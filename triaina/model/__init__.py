"""3D side: extrude a 2D design, build the knife mount, slice for printing.

Geometry uses manifold3d (exact booleans, holes by even-odd fill); slicing
runs the `prusa-slicer` command line with triaina/data/prusaslicer_neptune4.ini.
"""

from __future__ import annotations

import struct
from pathlib import Path


class ModelError(ValueError):
    """The model could not be built or sliced; the message says why."""


def write_stl(solid, path: Path) -> int:
    """Write a manifold3d Manifold as binary STL. Returns the triangle count."""
    mesh = solid.to_mesh()
    verts = mesh.vert_properties[:, :3]
    tris = mesh.tri_verts
    if len(tris) == 0:
        raise ModelError("the model is empty")
    with path.open("wb") as f:
        f.write(b"triaina".ljust(80, b"\0"))
        f.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            p0, p1, p2 = verts[a], verts[b], verts[c]
            ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            norm = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
            f.write(
                struct.pack(
                    "<12fH",
                    nx / norm,
                    ny / norm,
                    nz / norm,
                    *p0,
                    *p1,
                    *p2,
                    0,
                )
            )
    return len(tris)
