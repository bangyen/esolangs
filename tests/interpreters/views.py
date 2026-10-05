"""The VM's shared views, read off a bare machine with the VM's defaults.

``esolangs.vm`` reads ``ip``, ``memory`` and ``stack`` by ``getattr``, so an
interpreter with no stack or no addressable cells declares neither, and one
whose position is ``ind`` need not repeat it as ``ip``.  Observers that step a
``_Machine`` directly read the views through here to see what the VM shows.
"""


def view(machine: object, name: str) -> object:
    """Return ``machine.<name>``, else the VM's default for that view."""
    if hasattr(machine, name):
        return getattr(machine, name)
    if name == "ip":
        return getattr(machine, "ind", None)
    return []
