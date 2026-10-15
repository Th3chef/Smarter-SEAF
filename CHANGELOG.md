# Changelog

## 1.0.2

- **Fixed:** soldiers could shoot you while staggered, getting up or swinging their gun around. To stop that, the mod has to know which way each soldier's gun points. In 1.0.1 it often threw that away early in a mission, and for the rifle it never got it back, so that protection was off for most soldiers. It now always keeps it.

## 1.0.1

First release. A new brain for the SEAF soldiers run by your game:
- **Friendly Fire Safety:** they hold fire while you, a teammate, your sentries, another SEAF soldier or a civilian is in their line of fire, including while staggered or getting up. The option picks who's protected (helldivers, other troopers, or both).
- **Armor Intelligence:** they leave armor they can't hurt for later while there's something else to shoot, and shoot it anyway when there isn't. Specialists keep their one EAT for Chargers and heavier and for structures it can destroy. Nobody shoots Detector Towers.
- **Ping Targeting:** soldiers within 50 m of you go for the enemy you ping.
