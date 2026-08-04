# Geometry Signature Validation Design

## Context

ComponentSpec validation currently requires the stored strict-topology and engineering-geometry SHA-256 hashes to equal hashes recomputed from the reference STEP file. Forty-five components fail this exact comparison even though their STEP byte checksum matches and their stored topology, volume, bounding box, and center of mass still agree with fresh measurements within the declared dimensional tolerance. Recomputing a representative failure with both the pinned OCP 7.8.1.1 and the locally installed OCP 7.9.3 produces the same new hashes, but neither reproduces the stored hash.

The stored hashes therefore identify an exact historical measurement pipeline, not reliably the engineering identity of a component across platforms and native-library environments. Older component YAML also omits the surface-area value that participated in the stored hash, so the historical hash input cannot be audited completely.

## Goals

- Continue to reject a changed or corrupted reference STEP file.
- Continue to reject meaningful topology or geometry changes.
- Stop blocking validation when only an environment-sensitive exact hash differs.
- Preserve exact hashes as diagnostic evidence for reproducibility investigations.
- Return actionable warnings that explain why validation was allowed to continue.

## Non-goals

- Do not bulk-regenerate component signatures.
- Do not weaken the reference STEP byte checksum.
- Do not accept dimensional or topology changes outside the existing specification tolerances.
- Do not redesign the ComponentSpec schema in this change.

## Validation Design

Validation remains layered:

1. **Artifact identity:** The declared reference STEP SHA-256 must match the file bytes. A mismatch is an error.
2. **Engineering identity:** Fresh measurements are compared with `validation.geometry.measured`:
   - solids, shells, and faces must match exactly;
   - volume must remain within the existing relative tolerance, defaulting to `1e-6`;
   - bounding-box minimum, maximum, and size must remain within `dimensional_tolerance`;
   - center of mass must remain within `dimensional_tolerance`;
   - surface area is compared only when a stored surface-area measurement exists, using the same relative tolerance as volume.
   Any failed engineering comparison is an error.
3. **Exact reproducibility:** Strict-topology and engineering-geometry hashes are recomputed. A mismatch is a warning when artifact and engineering identity checks pass. Matching hashes produce no warning.

The existing `validate_spec` return shape remains `{errors: [...], warnings: [...]}`. Callers that already block on `errors` continue to work without API changes. CI will surface hash drift in logs while allowing verified geometry to pass.

## Error and Warning Semantics

- File SHA mismatch: `reference STEP SHA-256 不匹配` error.
- Engineering mismatch: a field-specific error naming topology, volume, surface area, bounding box, or center of mass.
- Hash-only mismatch: `reference STEP 精确几何签名不匹配；工程几何仍在声明公差内` warning.

Validation does not run later geometry checks when the artifact file is missing or its byte checksum fails, because the file is no longer the declared artifact.

## Testing

- A stale exact hash with unchanged STEP bytes and in-tolerance engineering measurements passes with one warning.
- Changed STEP bytes fail before geometry-signature handling.
- Changed stored solid/face topology fails.
- Volume outside the relative tolerance fails.
- Bounding-box or center-of-mass drift outside `dimensional_tolerance` fails.
- Matching hashes and measurements pass without warnings.
- The component-library validation script and the full component-spec test module pass against the current formal library.

## Rollout

No component YAML migration is required. Existing hashes remain available as historical diagnostics. A later ComponentSpec schema revision may add signature-algorithm metadata, normalized inputs, native-kernel version, and complete stored measurements; that future schema work is intentionally outside this fix.
