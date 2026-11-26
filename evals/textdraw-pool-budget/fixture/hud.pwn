// current HUD: per-player elements created as global TextDraws
new Text:gHealth[MAX_PLAYERS];
new Text:gArmour[MAX_PLAYERS];
new Text:gMoney[MAX_PLAYERS];

stock BuildHud(playerid)
{
    gHealth[playerid] = TextDrawCreate(320.0, 380.0, "LD_SPAC:white");
    gArmour[playerid] = TextDrawCreate(320.0, 395.0, "LD_SPAC:white");
    gMoney[playerid]  = TextDrawCreate(320.0, 410.0, "$0");
    TextDrawShowForPlayer(playerid, gHealth[playerid]);
    return 1;
}
