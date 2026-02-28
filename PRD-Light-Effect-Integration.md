# Product Requirements Document: Light Effect-Based Rako Integration

## Overview
Implement the RakoRooms Home Assistant integration using the Light platform with the effect property for scene control, allowing rooms to appear as standard lights while maintaining scene-based functionality.

## Background

### Current State
The integration currently creates two types of light entities per Rako room:
- **Room Light** (`RakoRoomLight`): Controls room scenes through brightness mapping (0-255 brightness maps to scenes 0-4)
- **Channel Lights** (`RakoChannelLight`): Individual channel controls (e.g., "Living Room - Channel 1", "Living Room - Channel 2")

### Problem Statement
The current approach doesn't align with how Rako lighting systems are designed to be used:
- Rako systems are scene-based, not individual dimmer-based
- Users configure scenes (1-4) with preset channel levels, not individual channels
- Exposing individual channels as separate lights creates clutter in Home Assistant
- The brightness-to-scene mapping (0-255 → scenes 0-4) is not intuitive for users
- Managing many individual channel entities is cumbersome and not the intended use case

### Alternative Considered
PRD-Scene-Based-Integration.md proposed using the Select platform, which works but:
- Doesn't integrate with Home Assistant's light ecosystem
- Cannot be controlled with standard light services (`light.turn_on`, `light.turn_off`)
- Doesn't appear in light-specific dashboards and groupings
- Doesn't benefit from light-specific automations and voice control patterns

## Goals
1. Simplify the integration to match Rako's scene-based paradigm
2. Integrate seamlessly with Home Assistant's light platform
3. Provide intuitive scene control through the effect property
4. Enable standard light services (`turn_on`, `turn_off`) for room control
5. Support "turn on to last scene" functionality automatically
6. Reduce entity clutter in Home Assistant

## Non-Goals
- Individual channel-level control (this functionality will be removed)
- Brightness dimming within scenes (scenes are preset configurations)
- Migration path for existing users (breaking change acceptable for major version)
- Color temperature or RGB control (not applicable to Rako scenes)

## Feature Requirements

### FR1: Light Entity with Scene Effects
**Priority: P0 (Must Have)**

Create a light entity for each Rako room using the effect property for scene selection.

**Details:**
- Each Rako room should expose a single light entity
- On/off state controls whether the room is in an active scene or off
- Effect list contains scenes: "Scene 1", "Scene 2", "Scene 3", "Scene 4"
- Current effect reflects the active scene
- When turned on without specifying effect, restore last active scene
- When turned off, store the current scene for restoration

**Acceptance Criteria:**
- User can turn light on/off using `light.turn_on` and `light.turn_off`
- User can select scene using `light.turn_on` with `effect` parameter
- Entity shows "on" when any scene 1-4 is active, "off" when scene is off
- Current scene is visible in the effect attribute
- Turning on restores the last non-off scene
- Entity appears in Home Assistant with appropriate device association

### FR2: Remove Channel-Level Entities
**Priority: P0 (Must Have)**

Remove all `RakoChannelLight` entities from the integration.

**Details:**
- Delete `RakoChannelLight` class from `light.py`
- Remove channel discovery logic from `async_setup_entry` in `light.py`
- Clean up any channel-specific code from `bridge.py`

**Acceptance Criteria:**
- No individual channel entities are created
- Only room-level light entities exist in Home Assistant
- Reduced number of entities per Rako installation

### FR3: Effect-Based Scene Control
**Priority: P0 (Must Have)**

Implement scene control through Home Assistant's light effect mechanism.

**Details:**
- Effect list: `["Scene 1", "Scene 2", "Scene 3", "Scene 4"]`
- Setting an effect activates the corresponding Rako scene
- Current effect property reflects the active scene (null when off)
- Support both `effect` parameter and direct scene activation
- Scene names should be clear and match Rako's standard naming

**Acceptance Criteria:**
- `light.turn_on` with `effect: "Scene 1"` activates Scene 1
- `light.turn_on` with `effect: "Scene 2"` activates Scene 2, etc.
- Effect attribute shows current scene when on
- Effect attribute is null/empty when light is off
- Invalid effect names are rejected with appropriate error

### FR4: Last Scene Memory
**Priority: P0 (Must Have)**

Automatically restore the last active scene when turning on without specifying an effect.

**Details:**
- Track the last non-off scene for each room
- When `light.turn_on` is called without effect parameter, restore last scene
- Default to Scene 1 if no previous scene exists
- Memory persists across Home Assistant restarts (use restore state)
- Memory updates every time a scene is activated

**Acceptance Criteria:**
- User activates Scene 3, turns off, then turns on → Scene 3 activates
- User turns on light without prior history → Scene 1 activates (default)
- Last scene memory survives Home Assistant restarts
- Scene memory updates when scene changed via Rako hardware
- Turning off and on quickly restores previous scene reliably

### FR5: State Synchronization
**Priority: P0 (Must Have)**

Maintain real-time state updates when scenes change outside Home Assistant.

**Details:**
- Continue listening to Rako Bridge UDP messages
- Update light state (on/off) and effect when `SceneStatusMessage` received
- Handle scene changes from Rako wall panels, keypads, or other controllers
- Preserve existing `listen_for_state_updates` architecture
- Update last scene memory when external changes occur

**Acceptance Criteria:**
- Scene changes from Rako hardware reflect in HA within 1 second
- On/off state updates correctly (on for scenes 1-4, off for scene 0)
- Effect attribute updates to show current scene
- No polling required (push-based updates only)
- State remains synchronized across multiple control sources

### FR6: Standard Light Service Support
**Priority: P0 (Must Have)**

Support all relevant standard light services.

**Details:**
- `light.turn_on`: Activate last scene (or default)
- `light.turn_on` with `effect`: Activate specific scene
- `light.turn_off`: Deactivate room (scene 0)
- `light.toggle`: Toggle between off and last scene
- Respond appropriately to unsupported features (brightness, color, etc.)

**Acceptance Criteria:**
- `light.turn_on` activates appropriate scene
- `light.turn_off` turns room off (scene 0)
- `light.toggle` works correctly
- Unsupported features (brightness, color) are ignored gracefully
- Services work in automations and scripts

### FR7: Device Association
**Priority: P1 (Should Have)**

Maintain proper device association in Home Assistant's device registry.

**Details:**
- Each room's light entity should be associated with a device
- Device should show manufacturer (Rako), area (room title), and connection to bridge
- Preserve existing device registry structure from `__init__.py`

**Acceptance Criteria:**
- Light entities appear under appropriate devices
- Device info includes room name, manufacturer
- Bridge device remains as parent/hub device

### FR8: Configuration & Discovery
**Priority: P0 (Must Have)**

Maintain existing configuration flow and automatic discovery.

**Details:**
- Keep current config flow (`config_flow.py`)
- Continue discovering rooms via `bridge.discover_lights()` or equivalent
- Create light entities for all discovered rooms automatically
- No additional user configuration required

**Acceptance Criteria:**
- Existing configuration remains valid
- All Rako rooms are discovered automatically
- Light entities created without manual intervention

## Technical Specifications

### Entity Structure
```python
Platform: light
Entity ID: light.{room_name}
Name: {Room Name}
State: on/off (on for scenes 1-4, off for scene 0)
Effect List: ["Scene 1", "Scene 2", "Scene 3", "Scene 4"]
Current Effect: "Scene 1" | "Scene 2" | "Scene 3" | "Scene 4" | None
Supported Features: SUPPORT_EFFECT
Icon: mdi:lightbulb-group
Device Class: None
```

### Light Attributes
```yaml
supported_features: 4  # SUPPORT_EFFECT
effect_list:
  - Scene 1
  - Scene 2
  - Scene 3
  - Scene 4
effect: "Scene 2"  # Current scene, or null when off
```

### Implementation Changes

**Files to Modify:**
- `custom_components/rakorooms/light.py`:
  - Modify `RakoRoomLight` to implement effect support
  - Remove `RakoChannelLight` class entirely
  - Add `supported_features` property returning `SUPPORT_EFFECT`
  - Add `effect_list` property returning scene names
  - Add `effect` property returning current scene
  - Implement `async_turn_on(self, **kwargs)` with effect parameter support
  - Implement last scene memory using `RestoreEntity`
  - Remove brightness-based scene mapping

- `custom_components/rakorooms/bridge.py`:
  - Update state update logic for scene-to-effect mapping
  - Ensure scene status messages properly update effect state

**Files to Keep:**
- `custom_components/rakorooms/__init__.py`: No platform change needed (stays as `LIGHT_DOMAIN`)
- `custom_components/rakorooms/config_flow.py`: No changes needed

### Data Flow: Setting a Scene via Effect

1. User calls `light.turn_on` with `effect: "Scene 3"` in HA UI or automation
2. HA calls `async_turn_on(effect="Scene 3")` on light entity
3. Entity maps "Scene 3" to scene number 3
4. Entity calls `bridge.set_room_scene(room_id, 3)`
5. Entity stores scene 3 as last active scene
6. Bridge sends command to Rako Bridge
7. Rako Bridge broadcasts scene change via UDP
8. Integration receives `SceneStatusMessage`
9. Entity state updates: state="on", effect="Scene 3"

### Data Flow: Turning On to Last Scene

1. User calls `light.turn_on` (no effect parameter)
2. HA calls `async_turn_on()` on light entity
3. Entity retrieves last scene from memory (e.g., Scene 2)
4. Entity calls `bridge.set_room_scene(room_id, 2)`
5. Same flow as above continues

### Data Flow: Turning Off

1. User calls `light.turn_off`
2. HA calls `async_turn_off()` on light entity
3. Entity calls `bridge.set_room_scene(room_id, 0)`
4. Bridge sends off command to Rako Bridge
5. Rako Bridge broadcasts scene change (scene 0) via UDP
6. Integration receives `SceneStatusMessage` with scene 0
7. Entity state updates: state="off", effect=None
8. Last scene memory is retained for next turn_on

### Scene Number Mapping

```python
SCENE_EFFECTS = {
    1: "Scene 1",
    2: "Scene 2",
    3: "Scene 3",
    4: "Scene 4",
}

EFFECT_TO_SCENE = {v: k for k, v in SCENE_EFFECTS.items()}

# Scene 0 = Off (not in effect list)
```

### Restore State Implementation

```python
from homeassistant.helpers.restore_state import RestoreEntity

class RakoRoomLight(LightEntity, RestoreEntity):
    async def async_added_to_hass(self):
        """Restore last scene when entity is added."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state and last_state.attributes.get("effect"):
            self._last_scene = EFFECT_TO_SCENE.get(
                last_state.attributes["effect"],
                1  # Default to Scene 1
            )
```

## User Experience Examples

### Voice Control
```
User: "Alexa, turn on Living Room"
→ Activates last scene (e.g., Scene 2)

User: "Hey Google, turn off Living Room"
→ Turns room off (scene 0)
```

### Automation Example
```yaml
automation:
  - alias: "Movie Mode"
    trigger:
      platform: state
      entity_id: input_boolean.movie_mode
      to: "on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.living_room
        data:
          effect: "Scene 4"
```

### Dashboard Control
- Appears in standard light controls
- Toggle on/off works intuitively
- Effect dropdown shows available scenes
- Works with light groups and areas

## Migration Considerations

### Breaking Changes
- Existing automations using `RakoChannelLight` entities will break
- Room light entity behavior changes (no brightness control, effect-based instead)
- This should be released as a major version (e.g., v2.0.0)

### Advantages Over Select Platform
- Integrates with light ecosystem (groups, voice control, etc.)
- Standard `light.turn_on`/`turn_off` semantics
- Automatic last scene restoration
- Better user experience for typical lighting use cases
- Works with existing light-based automations and dashboards

### User Communication
- Release notes must clearly state this is a breaking change
- Provide migration guide showing how to update automations
- Highlight benefits: simpler control, better integration, last scene memory
- Document effect-based scene selection

## Success Metrics
- Reduction in entity count (from N channels per room to 1 light per room)
- Improved user experience with standard light controls
- Positive feedback on last scene memory feature
- No increase in latency for scene changes
- Increased usage of voice control due to light platform integration

## Future Enhancements (Out of Scope)
- Custom scene naming (allow users to rename "Scene 1" to "Movie Mode")
- Scene programming via Home Assistant UI
- Support for additional Rako features (schedules, timers)
- Optional brightness dimming within scenes (if Rako supports it)
- Scene preview/editing capabilities

## Appendix

### Comparison: Light Effect vs. Select Platform

| Feature | Light Effect | Select |
|---------|-------------|--------|
| Standard light controls | ✅ Yes | ❌ No |
| Voice control integration | ✅ Native | ⚠️ Limited |
| Last scene memory | ✅ Built-in | ❌ Requires custom |
| Scene selection | Via effect | Via dropdown |
| Appears in light groups | ✅ Yes | ❌ No |
| Simple on/off | ✅ Intuitive | ⚠️ Less clear |
| Dashboard integration | ✅ Light cards | Select cards |

### Rako System Architecture
- Rako Bridge: Central hub communicating with Home Assistant
- Rooms: Logical grouping of channels
- Channels: Physical lighting circuits (1-4 per room typically)
- Scenes: Preset configurations (Off, 1, 2, 3, 4) with defined channel levels
- Wall Panels: Physical controls that activate scenes

### Home Assistant Light Effect Feature
The effect feature in Home Assistant's light platform is designed for:
- Color effects (e.g., "color loop", "rainbow")
- Pattern effects (e.g., "strobe", "flash")
- **Preset modes** (perfect for Rako scenes!)

This integration repurposes the effect feature for scene selection, which is semantically appropriate since Rako scenes are preset lighting modes.

---

**Document Version:** 1.0
**Date:** 2026-02-28
**Author:** Product Requirements
**Status:** Draft
