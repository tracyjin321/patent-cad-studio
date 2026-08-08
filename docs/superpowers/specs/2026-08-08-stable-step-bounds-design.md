# Stable STEP Bounds Design

## Goal

Make ComponentSpec validation and multi-round STEP validation agree while
preserving the existing 0.01 mm engineering tolerance. Re-exporting unchanged
geometry must not fail only because OpenCascade rewrote per-entity tolerance
metadata.

## Root cause

`inspect_shape()` currently builds bounds with `BRepBndLib.Add_s`. Those bounds
include the source shape tolerance. Two imported gear fixtures carry about
0.008054 mm of padding on each side; their AP242 re-export no longer carries
the same padding, so the derived size changes by 0.016108 mm even though solid
count, face count, volume, and surface area remain equivalent.

The multi-round report accepts 0.02 mm, while the formal ComponentSpec gate
uses each spec's 0.01 mm dimensional tolerance. The duplicated policies allow
the report and CI to disagree.

## Design

1. Add a focused helper that computes an axis-aligned geometric bounding box
   with `BRepBndLib.AddOptimal_s(..., useTriangulation=False,
   useShapeTolerance=False)`. This measures underlying geometry without STEP
   tolerance padding.
2. Expose the stable bound through an explicit `stable_bounds=True` measurement
   mode. Keep the default tolerance-aware measurement unchanged because the
   existing component library records that historical convention.
3. Add one shared engineering-measurement comparator in
   `app/component_spec.py`. Both stored-reference validation and STEP
   round-trip validation use it, so topology, volume, surface area, bounds,
   and center-of-mass have one policy.
4. Make the multi-round script import the same comparator and remove its
   independent 0.02 mm bounding-box constant.
5. Keep `dimensional_tolerance: 0.01` and relative tolerance `1e-6`. Do not add
   fixture-specific exceptions or globally loosen validation.

## Data compatibility

The checked-in YAML measurements were produced with tolerance-expanded bounds.
An audit found that changing the global default would force an unrelated
rebaseline across most of the component library. Therefore stored measurements
and signatures remain unchanged; only re-export equivalence checks opt into
stable bounds for both sides of the comparison.

## Testing

- A regression test must show both failing imported gear fixtures pass a forced
  STEP re-export with the 0.01 mm tolerance.
- A unit test must show shape-tolerance padding does not alter the stable
  bounding box.
- Existing tests that inject real bounding-box, topology, volume, and center
  drift must remain blocking.
- The exact CI commands must pass: component-library validation followed by
  the full pytest suite.

## Non-goals

- No relaxation of the 0.01 mm dimensional tolerance.
- No fixture-specific allowance for 0.016108 mm.
- No unrelated assembly, rendering, or catalog changes.
