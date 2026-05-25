"""Peer-to-peer federation: signed manifest exchange over MCP-over-HTTP.

Spec: openspec/changes/add-federation/proposal.md
"""

from .peers import (
    Peer,
    PeerError,
    PeersFile,
    add_peer,
    list_peers,
    read_peers,
    remove_peer,
    write_peers,
)
from .pull import PullError, fetch_manifest, pull_skill

__all__ = [
    "Peer",
    "PeerError",
    "PeersFile",
    "PullError",
    "add_peer",
    "fetch_manifest",
    "list_peers",
    "pull_skill",
    "read_peers",
    "remove_peer",
    "write_peers",
]
