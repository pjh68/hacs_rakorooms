# History
Integration Rako with Home Assistant has been a long voyage, with many captains.
This work build on that of:
@marengaz, who did all the hard graft, submitted in a PR to homeassistant core but subsequently abandoned when he lost access to his Rako system: https://github.com/home-assistant/core/pull/45915

@SimonLeigh, who resurrected and updated the core library and built a HACS package for custom instal of this integration 
https://github.com/SimonLeigh/hacs_rako

# Why another fork? And why Rako Rooms?
The fundamental design of Rako lighting systems and Home Assistant's view of lights doesn't quite align, particularly if you primarily want to retain control of your light configuration within Rako.

Rather than model Rako lights, this integration instead focusses on the scene setting of each room. Essentially, we model what is happening on the Rako light switches, not the light channels.

Rooms are modelled as Lights, with Scene details in the light's effect property.

Details of the changes are in [this PRD](PRD-Light-Effect-Integration.md)
