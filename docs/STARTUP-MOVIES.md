# Startup movie skip

Separate optional addon: `modLocalSkipStartupMovies`, requested October 1, 2026.
`python tools/startup_movies.py --install` derives one loose script from the
installed REDkit 5.0 source, verifies it with the official compiler together
with the currently installed mods, then installs it while Witcher is closed.

The only change removes `StartupMoviesMenu` from
`CR4Game.PopulateMenuQueueStartupOnce`. That menu queues the three PC startup
videos: disclaimers, legal and logo. The normal remaining menu queue runs next.
Loading recaps and story cinematics use their existing paths.

Game-derived scripts and compiled outputs remain under ignored `build/`.
The installation receipt and source/package/native hashes are in
`local/startup-movies-install.json`. The tool verifies existing mod file hashes
after installation. Native compilation is recorded separately from observed
launch behavior; a main-menu launch still needs user confirmation.

To uninstall, move only the directory
`E:\SteamLibrary\steamapps\common\The Witcher 3\Mods\modLocalSkipStartupMovies`
outside `Mods` while the game is closed. No original game files are replaced.
This does not change the anatomy addon package or its installation receipt.

Research found flAked's [Skip Movies](https://www.nexusmods.com/witcher3/mods/358),
updated for 5.0. This local addon was authored from the installed stock scripts;
it does not use or redistribute that author's mod files.
