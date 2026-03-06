import logging
import requests
import urllib3
from config import Config

logger = logging.getLogger(__name__)

if not Config.PROXMOX_VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ProxmoxAPI:
    def __init__(self):
        self.host = Config.PROXMOX_HOST
        self.node = Config.PROXMOX_NODE
        self.verify_ssl = Config.PROXMOX_VERIFY_SSL
        self.ticket = None
        self.csrf_token = None

    def _authenticate(self):
        resp = requests.post(
            f"{self.host}/api2/json/access/ticket",
            data={
                "username": Config.PROXMOX_USER,
                "password": Config.PROXMOX_PASSWORD,
            },
            verify=self.verify_ssl,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        self.ticket = data["ticket"]
        self.csrf_token = data["CSRFPreventionToken"]
        logger.debug("Proxmox authentication successful")

    def _request(self, method, path, **kwargs):
        if not self.ticket:
            self._authenticate()

        url = f"{self.host}/api2/json{path}"
        headers = {"CSRFPreventionToken": self.csrf_token}
        cookies = {"PVEAuthCookie": self.ticket}

        resp = requests.request(
            method, url, headers=headers, cookies=cookies, verify=self.verify_ssl, **kwargs
        )

        if resp.status_code == 401:
            self._authenticate()
            headers["CSRFPreventionToken"] = self.csrf_token
            cookies["PVEAuthCookie"] = self.ticket
            resp = requests.request(
                method, url, headers=headers, cookies=cookies, verify=self.verify_ssl, **kwargs
            )

        resp.raise_for_status()
        return resp.json().get("data")

    def get_next_vmid(self):
        return self._request("GET", "/cluster/nextid")

    def create_vm(self, vmid, name, cores, memory, disk_size, iso):
        logger.info("Creating VM %s (name=%s, cores=%s, mem=%s, disk=%s)", vmid, name, cores, memory, disk_size)
        return self._request(
            "POST",
            f"/nodes/{self.node}/qemu",
            data={
                "vmid": vmid,
                "name": name,
                "cores": cores,
                "memory": memory,
                "scsi0": f"local-lvm:{disk_size}",
                "cdrom": f"local:iso/{iso}",
                "net0": "virtio,bridge=vmbr0",
                "ostype": "l26",
                "start": 1,
            },
        )

    def start_vm(self, vmid):
        logger.info("Starting VM %s", vmid)
        return self._request("POST", f"/nodes/{self.node}/qemu/{vmid}/status/start")

    def stop_vm(self, vmid):
        logger.info("Stopping VM %s", vmid)
        return self._request("POST", f"/nodes/{self.node}/qemu/{vmid}/status/stop")

    def shutdown_vm(self, vmid):
        logger.info("Shutting down VM %s", vmid)
        return self._request("POST", f"/nodes/{self.node}/qemu/{vmid}/status/shutdown")

    def reboot_vm(self, vmid):
        logger.info("Rebooting VM %s", vmid)
        return self._request("POST", f"/nodes/{self.node}/qemu/{vmid}/status/reboot")

    def delete_vm(self, vmid):
        logger.info("Deleting VM %s", vmid)
        self.stop_vm(vmid)
        return self._request("DELETE", f"/nodes/{self.node}/qemu/{vmid}")

    def get_vm_status(self, vmid):
        return self._request("GET", f"/nodes/{self.node}/qemu/{vmid}/status/current")

    def resize_disk(self, vmid, disk, size):
        return self._request(
            "PUT",
            f"/nodes/{self.node}/qemu/{vmid}/resize",
            data={"disk": disk, "size": size},
        )

    def update_vm_config(self, vmid, **kwargs):
        return self._request(
            "PUT", f"/nodes/{self.node}/qemu/{vmid}/config", data=kwargs
        )

    def create_snapshot(self, vmid, name, description=""):
        logger.info("Creating snapshot '%s' for VM %s", name, vmid)
        return self._request(
            "POST",
            f"/nodes/{self.node}/qemu/{vmid}/snapshot",
            data={"snapname": name, "description": description},
        )

    def list_snapshots(self, vmid):
        return self._request("GET", f"/nodes/{self.node}/qemu/{vmid}/snapshot")

    def delete_snapshot(self, vmid, snapname):
        logger.info("Deleting snapshot '%s' for VM %s", snapname, vmid)
        return self._request(
            "DELETE", f"/nodes/{self.node}/qemu/{vmid}/snapshot/{snapname}"
        )

    def create_backup(self, vmid):
        logger.info("Creating backup for VM %s", vmid)
        return self._request(
            "POST",
            f"/nodes/{self.node}/vzdump",
            data={
                "vmid": vmid,
                "storage": "local",
                "compress": "zstd",
                "mode": "snapshot",
            },
        )

    def list_backups(self, vmid):
        storage_content = self._request(
            "GET",
            f"/nodes/{self.node}/storage/local/content",
            params={"content": "backup", "vmid": vmid},
        )
        return storage_content or []

    def get_backup_download_url(self, volid):
        """Return the API URL for downloading a backup volume."""
        return f"{self.host}/api2/json/nodes/{self.node}/storage/local/content/{volid}"

    def get_vm_vnc(self, vmid):
        return self._request(
            "POST", f"/nodes/{self.node}/qemu/{vmid}/vncproxy", data={"websocket": 1}
        )


proxmox = ProxmoxAPI()
