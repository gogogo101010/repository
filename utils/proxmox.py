import requests
import urllib3
from config import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ProxmoxAPI:
    def __init__(self):
        self.host = Config.PROXMOX_HOST
        self.node = Config.PROXMOX_NODE
        self.ticket = None
        self.csrf_token = None

    def _authenticate(self):
        resp = requests.post(
            f"{self.host}/api2/json/access/ticket",
            data={
                "username": Config.PROXMOX_USER,
                "password": Config.PROXMOX_PASSWORD,
            },
            verify=False,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        self.ticket = data["ticket"]
        self.csrf_token = data["CSRFPreventionToken"]

    def _request(self, method, path, **kwargs):
        if not self.ticket:
            self._authenticate()

        url = f"{self.host}/api2/json{path}"
        headers = {"CSRFPreventionToken": self.csrf_token}
        cookies = {"PVEAuthCookie": self.ticket}

        resp = requests.request(
            method, url, headers=headers, cookies=cookies, verify=False, **kwargs
        )

        if resp.status_code == 401:
            self._authenticate()
            headers["CSRFPreventionToken"] = self.csrf_token
            cookies["PVEAuthCookie"] = self.ticket
            resp = requests.request(
                method, url, headers=headers, cookies=cookies, verify=False, **kwargs
            )

        resp.raise_for_status()
        return resp.json().get("data")

    def get_next_vmid(self):
        return self._request("GET", "/cluster/nextid")

    def create_vm(self, vmid, name, cores, memory, disk_size, iso):
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
        return self._request("POST", f"/nodes/{self.node}/qemu/{vmid}/status/start")

    def stop_vm(self, vmid):
        return self._request("POST", f"/nodes/{self.node}/qemu/{vmid}/status/stop")

    def shutdown_vm(self, vmid):
        return self._request("POST", f"/nodes/{self.node}/qemu/{vmid}/status/shutdown")

    def reboot_vm(self, vmid):
        return self._request("POST", f"/nodes/{self.node}/qemu/{vmid}/status/reboot")

    def delete_vm(self, vmid):
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
        return self._request(
            "POST",
            f"/nodes/{self.node}/qemu/{vmid}/snapshot",
            data={"snapname": name, "description": description},
        )

    def list_snapshots(self, vmid):
        return self._request("GET", f"/nodes/{self.node}/qemu/{vmid}/snapshot")

    def delete_snapshot(self, vmid, snapname):
        return self._request(
            "DELETE", f"/nodes/{self.node}/qemu/{vmid}/snapshot/{snapname}"
        )

    def create_backup(self, vmid):
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

    def download_backup(self, volid):
        url = f"{self.host}/api2/json/nodes/{self.node}/storage/local/file-restore/download"
        headers = {"CSRFPreventionToken": self.csrf_token}
        cookies = {"PVEAuthCookie": self.ticket}
        return f"{self.host}/api2/json/nodes/{self.node}/storage/local/content/{volid}"

    def get_vm_vnc(self, vmid):
        return self._request(
            "POST", f"/nodes/{self.node}/qemu/{vmid}/vncproxy", data={"websocket": 1}
        )


proxmox = ProxmoxAPI()
