# Changelog

## 1.0.4

- **EATs only on heavy enemies:** specialists now only fire their one EAT at Chargers, Behemoths, Bile Titans, Impalers, Hulks, tanks, Factory and War Striders, Harvesters, Dragonroaches, Vox Engines, emplacements, and the structures it can destroy. Never at Stalkers, Alpha Commanders, Devastators, Scout Striders, Leviathans or Hive Lords. Before, a specialist could fire it at anything 4 seconds after the last heavy enemy he saw, or before the mod noticed he had drawn it. With nothing heavy around, a specialist who draws his EAT now holds his fire until the game has him put it away.
- **Lighter log writing:** the log file stays open instead of being reopened every time it's updated (about 2 ms saved each time).

## 1.0.3

- **Faster:** the mod does much less work for each soldier. What it reads from the game is read once a frame and shared, and soldiers who can't endanger anyone are checked a little less often: one with no target 20 times a second, one firing away from everyone 30 times a second. A soldier is still checked every frame the moment anyone is near his line of fire, his gun swings toward someone, he's staggered or he picks a new target. In testing it used about half the time overall, and the spike when a new squad drops in near you went from over 100 to about 60 ms a second.
- Friendly fire safety is unchanged: every friendly fire test gives the same results as 1.0.2.

## 1.0.2

- **Fixed:** soldiers could shoot you while staggered, getting up or swinging their gun around. To stop that, the mod has to know which way each soldier's gun points. In 1.0.1 it often threw that away early in a mission, and for the rifle it never got it back, so that protection was off for most soldiers. It now always keeps it.

## 1.0.1

First release. A new brain for the SEAF soldiers run by your game:
- **Friendly Fire Safety:** they hold fire while you, a teammate, your sentries, another SEAF soldier or a civilian is in their line of fire, including while staggered or getting up. The option picks who's protected (helldivers, other troopers, or both).
- **Armor Intelligence:** they leave armor they can't hurt for later while there's something else to shoot, and shoot it anyway when there isn't. Specialists keep their one EAT for Chargers and heavier and for structures it can destroy. Nobody shoots Detector Towers.
- **Ping Targeting:** soldiers within 50 m of you go for the enemy you ping.
