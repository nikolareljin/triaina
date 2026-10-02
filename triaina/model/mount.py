"""Parametric clamp for a Roland-style drag-knife holder.

A collar that grips the holder body (a slot closed by an M3 screw through two
clamp ears) on a flat plate with two slotted holes for bolting to the toolhead. It is a generic
starting point: measure your holder and your toolhead's screw positions, and
check the part against the Neptune 4 head before cutting with it. The holder
axis sits `standoff` mm in front of the plate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from triaina.model import ModelError

#: Clamp screw through the ears: M3 clearance hole, mm.
CLAMP_SCREW = 3.4
#: Each clamp ear's thickness either side of the slot, mm.
EAR_THICKNESS = 4.0


@dataclass
class MountOptions:
    #: Holder body diameter, mm (Roland-style holders: about 11.5).
    holder_diameter: float = 11.5
    #: Extra clearance on the bore, mm.
    clearance: float = 0.3
    wall: float = 4.0
    #: Collar height along the holder, mm.
    collar_height: float = 20.0
    #: Plate between the screw holes.
    plate_width: float = 40.0
    plate_thickness: float = 5.0
    #: Centre distance of the two mounting holes, mm.
    bolt_spacing: float = 30.0
    #: Through-hole for the mounting screws (M3: 3.4).
    bolt_hole: float = 3.4
    #: Holder axis distance from the plate's front face, mm.
    standoff: float = 12.0

    def check(self) -> None:
        bore = self.holder_diameter + self.clearance
        limits = {
            "holder_diameter": (4, 30),
            "wall": (2, 10),
            "collar_height": (8, 60),
            "plate_width": (20, 120),
            "plate_thickness": (3, 15),
            "bolt_spacing": (10, 110),
            "bolt_hole": (2, 8),
            "standoff": (5, 50),
        }
        bad = [k for k, (lo, hi) in limits.items() if not lo <= getattr(self, k) <= hi]
        if bad:
            raise ModelError(
                "out of range: " + ", ".join(f"{k} {limits[k][0]}-{limits[k][1]}" for k in bad)
            )
        if self.bolt_spacing + self.bolt_hole + 4 > self.plate_width:
            raise ModelError(
                "bolt holes do not fit the plate: widen the plate or reduce the spacing"
            )
        outer_r = bore / 2 + self.wall
        # Screws go in from the front: each hole, plus room for the screw head
        # (about twice the hole), must clear the collar and its bridge, or the
        # hole ends blind in the bridge and no screwdriver reaches it.
        if self.bolt_spacing / 2 - self.bolt_hole < outer_r:
            raise ModelError(
                "bolt holes would sit behind the collar: increase bolt spacing to at least"
                f" {2 * (outer_r + self.bolt_hole):.1f} mm, or reduce holder diameter/wall"
            )
        # The mounting holes are slotted 4 mm for height adjustment; with the
        # hole and 1.5 mm of material above and below, they must fit the height.
        need = 4.0 + self.bolt_hole + 3.0
        if self.collar_height < need:
            raise ModelError(
                f"collar height must be at least {need:.1f} mm for {self.bolt_hole} mm"
                " slotted mounting holes"
            )
        if self.standoff < bore / 2 + 1:
            raise ModelError("standoff too small: the bore would cut into the plate")
        if self.plate_thickness + self.standoff - outer_r < 0:
            raise ModelError(
                "standoff too small: the collar would stick out behind the plate into the toolhead"
            )


def build(opts: MountOptions):
    """Returns the mount as a manifold3d.Manifold, oriented to print without
    supports: standing on its bottom face, collar axis vertical, so the bore
    is round and only the small horizontal screw holes bridge."""
    import manifold3d as m

    opts.check()
    bore_r = (opts.holder_diameter + opts.clearance) / 2
    outer_r = bore_r + opts.wall
    h = opts.collar_height
    seg = 96

    # Plate: lying in X (width) x Y (thickness), standing h tall in Z.
    plate = m.Manifold.cube((opts.plate_width, opts.plate_thickness, h)).translate(
        (-opts.plate_width / 2, 0, 0)
    )
    # Collar centred `standoff` in front of the plate face (Y = plate_thickness).
    cy = opts.plate_thickness + opts.standoff
    collar = m.Manifold.cylinder(h, outer_r, outer_r, seg).translate((0, cy, 0))
    bridge = m.Manifold.cube((2 * outer_r, cy, h)).translate((-outer_r, 0, 0))
    # Clamp ears: two lugs in front of the collar either side of the slot,
    # with the clamp screw across them. Through the collar wall instead, a
    # screw wider than the wall would break into the bore and clamp nothing.
    ear_len = CLAMP_SCREW + 5.0
    ear_w = 1.5 + 2 * EAR_THICKNESS
    ears = m.Manifold.cube((ear_w, ear_len + 1.0, h)).translate((-ear_w / 2, cy + outer_r - 1.0, 0))
    body = plate + collar + bridge + ears

    bore = m.Manifold.cylinder(h + 2, bore_r, bore_r, seg).translate((0, cy, -1))
    # Slot through the front of the collar and between the ears.
    slot = m.Manifold.cube((1.5, outer_r + ear_len + 2, h + 2)).translate((-0.75, cy, -1))
    screw = (
        m.Manifold.cylinder(ear_w + 2, CLAMP_SCREW / 2, CLAMP_SCREW / 2, 32)
        .rotate((0, 90, 0))
        .translate((-(ear_w / 2 + 1), cy + outer_r + ear_len / 2, h / 2))
    )
    holes = m.Manifold()
    for x in (-opts.bolt_spacing / 2, opts.bolt_spacing / 2):
        # Slotted vertically by 4 mm so the knife height can be adjusted.
        for dz in (-2.0, 2.0):
            holes += (
                m.Manifold.cylinder(
                    opts.plate_thickness + 2, opts.bolt_hole / 2, opts.bolt_hole / 2, 32
                )
                .rotate((-90, 0, 0))
                .translate((x, -1, h / 2 + dz))
            )
        holes += m.Manifold.cube((opts.bolt_hole, opts.plate_thickness + 2, 4)).translate(
            (x - opts.bolt_hole / 2, -1, h / 2 - 2)
        )
    part = body - bore - slot - screw - holes
    if part.is_empty() or part.volume() <= 0:
        raise ModelError("mount geometry is empty; check the parameters")
    return part


def describe(opts: MountOptions) -> dict:
    return asdict(opts)
