# Axiom Unity Body — Rig & Prefab Specification v0.1

**Status:** Reference implementation  
**Visual source:** Approved simplified Axiom Unity-ready model sheet  
**Rule:** The canonical character design is frozen. Do not reinterpret head, ears, proportions, colors, hands, feet, torso, or tail during implementation.

## 1. Scale

- 1 Unity unit = 1 meter.
- Reference height: approximately 0.9 m.
- Minor scale changes are permitted; proportions are not.

## 2. Logical mesh regions

```text
Axiom_Body
├── Head
├── Ear_L
├── Ear_R
├── Eye_L
├── Eye_R
├── Torso
├── Arm_L
├── Arm_R
├── Hand_L
├── Hand_R
├── Leg_L
├── Leg_R
├── Foot_L
├── Foot_R
├── Tail
├── Collar
└── ChestCore
```

Keep these independently addressable where practical:
- Eyes
- ChestCore
- Collar
- TailFX / emissive tail layer

## 3. Skeleton

```text
Root
└── Pelvis
    ├── Spine_01
    │   └── Spine_02
    │       └── Chest
    │           ├── Neck
    │           │   └── Head
    │           │       ├── Ear_L_01
    │           │       │   └── Ear_L_02
    │           │       ├── Ear_R_01
    │           │       │   └── Ear_R_02
    │           │       ├── Eye_L
    │           │       └── Eye_R
    │           ├── Clavicle_L
    │           │   └── UpperArm_L
    │           │       └── LowerArm_L
    │           │           └── Hand_L
    │           └── Clavicle_R
    │               └── UpperArm_R
    │                   └── LowerArm_R
    │                       └── Hand_R
    ├── UpperLeg_L
    │   └── LowerLeg_L
    │       └── Foot_L
    │           └── Toe_L
    ├── UpperLeg_R
    │   └── LowerLeg_R
    │       └── Foot_R
    │           └── Toe_R
    └── Tail_01
        └── Tail_02
            └── Tail_03
                └── Tail_04
                    └── Tail_05
```

Non-deforming control targets:
- LookTarget
- AttentionTarget
- HandIK_L / HandIK_R
- FootIK_L / FootIK_R

## 4. Tail

Minimum 5 deform bones. The Mind never controls tail bones directly.

Semantic states include:
- neutral
- curious
- happy
- excited
- concerned
- relaxed

The Unity body maps these states to physical motion.

## 5. Ears

Each ear uses two bones:
- Ear_L_01 / Ear_L_02
- Ear_R_01 / Ear_R_02

Semantic states:
- neutral
- forward
- alert
- relaxed
- down
- asymmetric

## 6. Face

Use blendshapes for the initial implementation.

Minimum blendshapes:
- Blink_L / Blink_R
- EyeWide_L / EyeWide_R
- BrowUp_L / BrowUp_R
- BrowDown_L / BrowDown_R
- Smile / SmileWide
- Frown
- MouthOpen / MouthNarrow / MouthWide
- CheekRaise
- Squint_L / Squint_R

Minimum visemes:
- REST
- A
- E
- I
- O
- U
- M_B_P
- F_V
- L
- W_Q

## 7. Canonical prefab

`AxiomBody.prefab`

```text
AxiomBody
├── Model
│   ├── BodyMesh
│   ├── Eye_L
│   ├── Eye_R
│   ├── Collar
│   ├── ChestCore
│   └── TailFX
├── Rig
│   └── Root
├── Targets
│   ├── LookTarget
│   ├── AttentionTarget
│   ├── HandIK_L
│   ├── HandIK_R
│   ├── FootIK_L
│   └── FootIK_R
├── Audio
│   ├── VoiceSource
│   └── SpatialAudioSource
├── Sensors
│   ├── CameraAnchor
│   ├── EyeOrigin_L
│   ├── EyeOrigin_R
│   └── AudioListenerAnchor
└── Runtime
    ├── AxiomBodyController
    ├── AxiomExpressionController
    ├── AxiomLookController
    ├── AxiomSpeechController
    ├── AxiomTailController
    ├── AxiomEarController
    └── AxiomBodySensors
```

## 8. Animator layers

- Base Locomotion
- Upper Body
- Gesture
- Face
- Ears
- Tail
- Attention

Initial states:
- Idle
- Walk
- Turn
- Sit
- StandUp
- SitDown
- Listen
- Think
- Speak
- Acknowledge
- Wave
- Point
- Celebrate
- Concerned

Suggested parameters:
- `float Speed`
- `float Turn`
- `bool IsSpeaking`
- `bool IsListening`
- `bool IsThinking`
- `bool IsSitting`
- `float Attention`
- `float EmotionIntensity`
- `int Emotion`
- `int Gesture`
- triggers: `Acknowledge`, `Wave`, `Point`

## 9. Reference body boundary

Unity owns:
- mesh
- rig
- animation
- IK
- lip sync
- gaze
- ears
- tail
- materials
- rendering
- audio playback
- physical movement

Axiom Mind owns:
- identity
- memory
- attention
- intent
- emotion/context
- decision-making
- speech content
- experience
- journal

The interface between them is semantic.
