# Friction Disc CFD Simulation — OpenFOAM 12

Two-phase oil/air flow simulation of a rotating wet friction disc in a closed oil bath, using Volume of Fluid (VoF) and Non-Conformal Coupling (NCC) sliding mesh.

---

## 1. Aim

Wet clutch and differential systems rely on accurate drag torque prediction to optimize cooling groove design and minimize parasitic losses. This simulation builds a baseline multiphase CFD model for a rotating friction disc in an oil bath, with planned extensions toward turbulent flow and conjugate heat transfer.

**Key objectives:**
- Two-phase flow (oil/air) using VoF
- Rotating sliding mesh via NCC interface
- Drag torque extraction as a function of time
- Visualisation of oil distribution and velocity field

---

## 2. Physical Setup

| Parameter | Value |
|---|---|
| Disc OD radius | 103.2 mm |
| Disc ID radius | 88.4 mm |
| Disc thickness | ~1.9 mm |
| Rotation axis | Z |
| Rotation speed | 100 RPM |
| Oil fill level | 40% → Y = −0.0206 m |
| Gravity | −Y direction |
| NCC cylinder radius | 120 mm |
| NCC cylinder Z extent | ±30 mm (exceeds domain ±25 mm) |

**Fluid properties:**

| Property | Oil | Air |
|---|---|---|
| Density (kg/m³) | 860 | 1.2 |
| Kinematic viscosity (m²/s) | 46×10⁻⁶ | 1.48×10⁻⁵ |
| Surface tension (N/m) | 0.032 | — |

**Domain:** ±150 mm (X/Y), ±25 mm (Z)

---

## 3. Meshing Workflow

Follows the OpenFOAM 12 **propeller tutorial** for NCC meshing and the **rotatingCube tutorial** for VoF boundary conditions.

```bash
blockMesh
surfaceFeatures
snappyHexMesh -overwrite
cp -r constant/polyMesh constant/polyMesh_snappy_backup
createBaffles -overwrite
createNonConformalCouples -overwrite AMI_stationary AMI_rotating
setFields
decomposePar -cellProc
mpirun -np 8 foamRun -parallel > log.foamRun 2>&1 &
reconstructPar -cellProc
```

> **Note:** `-cellProc` is required for both `decomposePar` and `reconstructPar` when using NCC meshes.

---

## 4. Meshing Details

### STL Files (`constant/geometry/`)

| File | Description | Requirement |
|---|---|---|
| `fric_assembly.stl` | Friction disc geometry | Centred at origin, metres |
| `AMI_part.stl` | NCC sliding cylinder | **Closed** (with caps), r=120 mm, Z=±30 mm |

> **Critical:** `AMI_part.stl` must be a **closed watertight surface** with Z extent **exceeding the domain** (±25 mm). Z=±30 mm was used. Without caps, snappyHexMesh cannot create the cellZone/faceZone automatically.

### Key snappyHexMeshDict Settings

```c++
geometry
{
    AMI_part       { type triSurfaceMesh; file "AMI_part.stl"; }
    fric_assembly  { type triSurfaceMesh; file "fric_assembly.stl"; }
}

refinementSurfaces
{
    AMI_part
    {
        level (2 2);
        cellZone    innerCylinder;
        faceZone    innerCylinder;
        mode        inside;
    }
    fric_assembly { level (3 3); }
}

features
{
    { file "fric_assembly.eMesh"; level 4; }
    { file "AMI_part.eMesh";      level 2; }
}

insidePoint (0.0 0.13 0.0);   // Outside r=0.12m cylinder
allowFreeStandingZoneFaces false;
```

### createBafflesDict

```c++
baffles
{
    nonCouple
    {
        type     faceZone;
        zoneName innerCylinder;
        patches
        {
            owner    { name AMI_stationary; type wall; }
            neighbour{ name AMI_rotating;   type wall; }
        }
    }
}
```

> `type wall` assigns `inGroups: (wall nonCouple)` to both patches — this is essential for boundary conditions to survive `setFields` rewriting `alpha.oil`.

### Mesh Quality

| Metric | Value |
|---|---|
| Total cells | ~614,000 |
| Max non-orthogonality | 65° |
| Max skewness | 4.87 (7 faces) |
| NCC avg error | 0.000285 |
| NCC avg angle | 0.0005° |
| NCC face count | 32,952 |

---

## 5. Model and Solver

**Solver:** `foamRun -solver incompressibleVoF`  
**Turbulence:** Laminar (Stokes)

### dynamicMeshDict

```c++
mover
{
    type            motionSolver;
    libs            ("libfvMotionSolvers.so");
    motionSolver    solidBody;
    cellZone        innerCylinder;
    solidBodyMotionFunction rotatingMotion;
    origin          (0 0 0);
    axis            (0 0 1);
    omega           100 [rpm];
}
```

### Boundary Conditions

| Field | Patch | Type |
|---|---|---|
| `alpha.oil` | wall group (incl. AMI) | `zeroGradient` |
| `alpha.oil` | atmosphere | `inletOutlet` |
| `p_rgh` | wall group (incl. AMI) | `fixedFluxPressure` |
| `p_rgh` | atmosphere | `prghEntrainmentPressure` |
| `U` | tankFloor / tankWall_* | `noSlip` |
| `U` | fric_assembly patches | `movingWallVelocity` |
| `U` | nonCouple (AMI patches) | `movingWallSlipVelocity` |
| `U` | atmosphere | `pressureInletOutletVelocity` |

> `#includeEtc "caseDicts/setConstraintTypes"` handles `nonConformalCyclic` and `nonConformalError` patches automatically — no explicit entries needed.

### fvSolution (PIMPLE)

```c++
PIMPLE
{
    momentumPredictor       no;
    nOuterCorrectors        1;
    nCorrectors             1;
    nNonOrthogonalCorrectors 0;
    correctPhi              yes;
    correctMeshPhi          no;
}
```

---

## 6. Challenges and Debugging

### snappyHexMesh — Region Name Error
**Error:** `Unknown region name AMI_part, valid: zone0`  
**Fix:** Remove the `regions` block from the geometry section — unnamed STL regions default to `zone0`.

### createBaffles — 0 Faces Converted
**Error:** `Converted 0 faces into boundary faces`  
**Fix:** Regenerate `AMI_part.stl` as a closed watertight cylinder with top and bottom caps.

### snappyHexMesh — Too Many Regions
**Error:** `valid: patch24295, patch24296...`  
**Fix:** Export STL as a single unified region, or remove the `regions` block.

### setFields Dropping Boundary Conditions
**Error:** `Cannot find patchField entry for AMI_stationary` at runtime  
**Fix:** Change AMI patch type to `wall` in `createBafflesDict`. This assigns `inGroups: (wall nonCouple)` so the `wall {}` group entry in `0/` files covers them and survives `setFields` binary rewrite.

### NCC Coverage = 0 — Simulation Blowup
**Error:** `Target min coverage = 0`, Courant > 200, torque → 10²⁴ at t≈0.002s  
**Fix:** Regenerate `AMI_part.stl` with Z=±30 mm. The original Z=±12.5 mm was smaller than the domain Z=±25 mm, leaving faces at the cylinder radius with no NCC coupling partner.

### Velocity Blowup — Wrong BC on AMI Interface
**Error:** Courant max > 242, torque explosion  
**Fix:** Use `movingWallSlipVelocity` for the `nonCouple` group in `0/U` (from propeller tutorial). `noSlip` forces velocity=0 on rotating mesh faces, conflicting with mesh motion.

### Path with Spaces — snappyHexMesh Abort
**Error:** `fileName::stripInvalid() called for invalid fileName`  
**Fix:** Move the case to a directory path with no spaces or special characters.

### Periodic Torque Spikes
**Observation:** Torque spikes every ~0.6s (= 1 rotation period)  
**Cause:** NCC coverage drops to ~0.91 as 7 skew mesh faces rotate through the interface.  
**Mitigation:** Improve mesh quality, increase `nNonOrthogonalCorrectors`.

---

## 7. Results

| Metric | Value |
|---|---|
| Simulation end time | 2.0 s (3.3 disc rotations) |
| Wall clock time | ~3.2 hours (8 cores, 614k cells) |
| Steady state viscous torque Mz | ~−0.028 N·m (average, excluding spikes) |
| Oil volume fraction | 0.431 (stable) |
| Max Courant number | < 0.5 (stable) |
| Typical deltaT | ~7.5×10⁻⁵ s |

In a closed bath, torque decreases over time as the oil spins up with the disc. The average value of ~0.028 N·m is the best engineering estimate from this simulation.

---

## 8. Suggestions for Improvement

- **Mesh:** Refine at AMI cylinder (r=120 mm) to reduce NCC coverage drops and torque spikes
- **Mesh:** Target max skewness < 2 to eliminate periodic artifacts
- **Solver:** Increase `nNonOrthogonalCorrectors` to 2 for better handling of skew faces
- **Solver:** Increase `nAlphaSubCycles` from 3 to 5 for sharper oil/air interface
- **Physics:** Enable k-omega SST turbulence for higher RPM cases
- **Study:** Parametric sweep over RPM and fill level
- **Validation:** Compare against analytical parallel disc torque formula

---

## Key NCC Learnings (OpenFOAM 12)

- Closed watertight STL required for snappy to auto-create cellZone/faceZone (`topoSet` not needed)
- STL cylinder Z must exceed domain Z extent (5 mm buffer recommended)
- `createBaffles` patch `type wall` → `inGroups: (wall nonCouple)` → BC group coverage works
- `decomposePar -cellProc` and `reconstructPar -cellProc` both required for NCC
- `movingWallSlipVelocity` is the correct BC for the NCC sliding interface
- `#includeEtc "caseDicts/setConstraintTypes"` handles all constraint patches automatically
- `setFields` rewrites `alpha.*` in binary — patch entries must be covered by a group to survive
- Case directory path must not contain spaces

---

## File Structure

```
case/
├── 0/
│   ├── alpha.oil
│   ├── p_rgh
│   └── U
├── constant/
│   ├── geometry/
│   │   ├── AMI_part.stl        ← closed cylinder, r=120mm, Z=±30mm
│   │   └── fric_assembly.stl
│   ├── dynamicMeshDict
│   ├── phaseProperties
│   ├── physicalProperties.oil
│   └── physicalProperties.air
└── system/
    ├── blockMeshDict
    ├── snappyHexMeshDict
    ├── createBafflesDict
    ├── controlDict
    ├── fvSchemes
    ├── fvSolution
    ├── setFieldsDict
    ├── decomposeParDict
    └── functions            ← torque function object
```


<img width="555" height="298" alt="image" src="https://github.com/user-attachments/assets/d85dd9f7-2df1-4116-ae54-b734cf20ef06" />
</figcaption>This is your image caption</figcaption>
<img width="555" height="298" alt="image" src="https://github.com/user-attachments/assets/41f7fdf0-5a1a-4539-a110-a4af1e39c2ec" />
<img width="555" height="298" alt="image" src="https://github.com/user-attachments/assets/1964ad0e-f7b5-4077-86ac-781b63972e70" />
<img width="555" height="298" alt="viscous_torque_z" src="https://github.com/user-attachments/assets/b8b038c4-79e8-4e4a-b5b7-7d59c1b0100a" />

---

*OpenFOAM 12 | incompressibleVoF | NCC Sliding Mesh | Two-Phase Flow*
