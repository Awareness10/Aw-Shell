"""Fabric's HyprlandWorkspaces, for workspaces without an "id".

Hyprland 0.57 leaves "id" out of special workspaces (special:magic) in
`j/workspaces` and in a client's "workspace". Fabric reads it on every
workspace, so the bar crashed on startup while the scratchpad was open.
Special workspaces never get a button, so they're skipped.
"""

import json

from fabric.hyprland.widgets import HyprlandWorkspaces as FabricWorkspaces
from loguru import logger


class HyprlandWorkspaces(FabricWorkspaces):
    def on_ready(self, *_):
        workspaces = json.loads(self.connection.send_command("j/workspaces").reply.decode())
        active = json.loads(self.connection.send_command("j/activeworkspace").reply.decode())
        for workspace in workspaces:
            if (workspace_id := workspace.get("id")) is None:
                continue
            self.workspace_created(workspace_id)
            if workspace_id == active.get("id"):
                self.workspace_activated(workspace_id)

    def on_urgent(self, _, event):
        if len(event.data) != 1:
            return
        clients = json.loads(self.connection.send_command("j/clients").reply.decode())
        client = next((c for c in clients if c["address"] == "0x" + event.data[0]), {})
        if not (workspace := client.get("workspace")):
            return logger.warning(
                f"[Workspaces] urgent signal for an unknown window ({event.data[0]}), skipping"
            )
        if (workspace_id := workspace.get("id")) is not None:
            self.urgent(int(workspace_id))
