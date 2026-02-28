# Product Requirements Document: Scene-Based Rako Integration

## Overview
Simplify the RakoRooms Home Assistant integration to focus exclusively on room-based scene control, removing individual channel-level light entities.

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

## Goals
1. Simplify the integration to match Rako's scene-based paradigm
2. Reduce entity clutter in Home Assistant
3. Provide a clearer, more intuitive user experience for controlling Rako rooms
4. Maintain compatibility with Home Assistant's automation and scripting capabilities

## Non-Goals
- Individual channel-level control (this functionality will be removed)
- Brightness dimming within scenes (scenes are preset configurations)
- Migration path for existing users (breaking change acceptable for major version)

## Feature Requirements

### FR1: Scene Selection Entity
**Priority: P0 (Must Have)**

Create a scene selection mechanism for each Rako room using Home Assistant's native scene platform or select entity.

**Details:**
- Each Rako room should expose a single entity for scene control
- Scenes should be labeled clearly: "Off", "Scene 1", "Scene 2", "Scene 3", "Scene 4"
- Entity should reflect the current active scene in the room
- Scene changes should be pushed to Home Assistant in real-time (maintain existing UDP listener functionality)

**Acceptance Criteria:**
- User can select any of 5 scene options (Off, 1-4) per room
- Scene selection immediately triggers the corresponding Rako command
- Current scene state updates when changed via Rako wall panels or other controllers
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
- Only room-level entities exist in Home Assistant
- Reduced number of entities per Rako installation

### FR3: Platform Selection
**Priority: P0 (Must Have)**

Determine the most appropriate Home Assistant platform for scene control.

**Options:**
1. **Scene Platform**: Use HA's native scene platform
   - Pros: Semantically correct, scenes are activate-only (no state)
   - Cons: Scenes traditionally don't show current state in HA

2. **Select Platform**: Use select entity with scene options
   - Pros: Shows current scene, clear UI, stateful
   - Cons: Not the traditional "scene" semantic in HA

3. **Modified Light Platform**: Keep as light but with discrete scene levels
   - Pros: Maintains some backwards compatibility
   - Cons: Semantically incorrect (not really a "light")

**Recommendation**: Select Platform
- Most intuitive for users (dropdown with current scene visible)
- Aligns with Rako's stateful scene model
- Better UX than activation-only scenes

**Acceptance Criteria:**
- Platform choice is documented and implemented
- Entity type is appropriate for scene selection
- Works with Home Assistant automations and scripts

### FR4: State Synchronization
**Priority: P0 (Must Have)**

Maintain real-time state updates when scenes change outside Home Assistant.

**Details:**
- Continue listening to Rako Bridge UDP messages
- Update scene entity state when `SceneStatusMessage` received
- Handle scene changes from Rako wall panels, keypads, or other controllers
- Preserve existing `listen_for_state_updates` architecture

**Acceptance Criteria:**
- Scene changes from Rako hardware reflect in HA within 1 second
- No polling required (push-based updates only)
- State remains synchronized across multiple control sources

### FR5: Device Association
**Priority: P1 (Should Have)**

Maintain proper device association in Home Assistant's device registry.

**Details:**
- Each room's scene selector should be associated with a device
- Device should show manufacturer (Rako), area (room title), and connection to bridge
- Preserve existing device registry structure from `__init__.py`

**Acceptance Criteria:**
- Scene entities appear under appropriate devices
- Device info includes room name, manufacturer
- Bridge device remains as parent/hub device

### FR6: Configuration & Discovery
**Priority: P0 (Must Have)**

Maintain existing configuration flow and automatic discovery.

**Details:**
- Keep current config flow (`config_flow.py`)
- Continue discovering rooms via `bridge.discover_lights()` or equivalent
- Create scene entities for all discovered rooms automatically
- No additional user configuration required

**Acceptance Criteria:**
- Existing configuration remains valid
- All Rako rooms are discovered automatically
- Scene entities created without manual intervention

## Technical Specifications

### Entity Structure (Recommended: Select Platform)
```python
Platform: select
Entity ID: select.{room_name}_scene
Name: {Room Name} Scene
Options: ["Off", "Scene 1", "Scene 2", "Scene 3", "Scene 4"]
Current State: One of the above options
Icon: mdi:lightbulb-group
Device Class: None (or custom)
```

### Implementation Changes

**Files to Modify:**
- `custom_components/rakorooms/__init__.py`: Change platform from `LIGHT_DOMAIN` to `SELECT_DOMAIN`
- `custom_components/rakorooms/light.py`: Delete or rename to `select.py`, remove `RakoChannelLight`
- `custom_components/rakorooms/bridge.py`: Update state update logic for scenes only

**Files to Create (if using Select platform):**
- `custom_components/rakorooms/select.py`: New platform implementation

### Data Flow
1. User selects scene from dropdown in HA UI
2. HA calls `async_select_option()` on entity
3. Entity calls `bridge.set_room_scene(room_id, scene)`
4. Bridge sends command to Rako Bridge
5. Rako Bridge broadcasts scene change via UDP
6. Integration receives `SceneStatusMessage`
7. Entity state updates to reflect new scene

## Migration Considerations

### Breaking Changes
- Existing automations using `RakoChannelLight` entities will break
- Entity IDs will change (from `light.room_name_channel_x` to `select.room_name_scene`)
- This should be released as a major version (e.g., v2.0.0)

### User Communication
- Release notes must clearly state this is a breaking change
- Provide migration guide in documentation
- Consider maintaining both versions for a transition period

## Success Metrics
- Reduction in entity count (from N channels per room to 1 scene selector per room)
- Simplified user configuration (fewer entities to manage)
- Positive user feedback on scene-based control model
- No increase in latency for scene changes

## Future Enhancements (Out of Scope)
- Custom scene naming (allow users to rename "Scene 1" to "Movie Mode")
- Scene programming via Home Assistant UI
- Support for additional Rako features (schedules, timers)
- Integration with Home Assistant's native scene system

## Appendix

### Scene to Brightness Mapping (Current)
The current implementation uses this mapping in `python_rako.helpers`:
- Off: 0 brightness (0)
- Scene 1: 64 brightness (25%)
- Scene 2: 128 brightness (50%)
- Scene 3: 192 brightness (75%)
- Scene 4: 255 brightness (100%)

This mapping is unintuitive and will be replaced with explicit scene selection.

### Rako System Architecture
- Rako Bridge: Central hub communicating with Home Assistant
- Rooms: Logical grouping of channels
- Channels: Physical lighting circuits (1-4 per room typically)
- Scenes: Preset configurations (Off, 1, 2, 3, 4) with defined channel levels
- Wall Panels: Physical controls that activate scenes

---

**Document Version:** 1.0
**Date:** 2026-02-28
**Author:** Product Requirements
**Status:** Draft
