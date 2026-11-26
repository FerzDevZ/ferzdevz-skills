new gKills[MAX_PLAYERS];

public OnPlayerDeath(playerid, killerid, reason)
{
    if (killerid != INVALID_PLAYER_ID)
    {
        gKills[killerid]++;
        GivePlayerMoney(killerid, 500);
    }
    return 1;
}
