// Compile gate for the skill library: every pattern below comes from a skill.
// If a signature drifts, this file stops compiling and the gate fails.
#include <open.mp>

new PlayerText:g_HudValue[MAX_PLAYERS];
new Text:g_Banner;
new Menu:g_Menu;
new g_PlayerCount;

forward TickSample();

public OnGameModeInit()
{
    g_Banner = TextDrawCreate(320.0, 20.0, "Server");
    TextDrawAlignment(g_Banner, TEXT_DRAW_ALIGN_CENTRE);
    TextDrawLetterSize(g_Banner, 0.25, 1.0);
    TextDrawTextSize(g_Banner, 200.0, 20.0);
    TextDrawSetOutline(g_Banner, 0);
    TextDrawSetShadow(g_Banner, 0);
    TextDrawBackgroundColour(g_Banner, 0x00000000);
    TextDrawColour(g_Banner, 0xFFFFFFFF);
    TextDrawUseBox(g_Banner, false);
    TextDrawShowForAll(g_Banner);

    g_Menu = CreateMenu("Pilih", 1, 200.0, 150.0, 180.0, 120.0);
    AddMenuItem(g_Menu, 0, "Satu");
    AddMenuItem(g_Menu, 0, "Dua");
    SetMenuColumnHeader(g_Menu, 0, "Aksi");

    SetTimer("TickSample", 1000, true);
    return 1;
}

public OnPlayerConnect(playerid)
{
    g_HudValue[playerid] = CreatePlayerTextDraw(playerid, 20.0, 300.0, "0");
    PlayerTextDrawLetterSize(playerid, g_HudValue[playerid], 0.2, 0.9);
    PlayerTextDrawColour(playerid, g_HudValue[playerid], 0xFFFFFFFF);
    PlayerTextDrawShow(playerid, g_HudValue[playerid]);
    g_PlayerCount++;
    return 1;
}

public OnPlayerSelectedMenuRow(playerid, row)
{
    if (row == 0) SendClientMessage(playerid, 0xFFFFFFFF, "satu");
    return 1;
}

public TickSample()
{
    new str[16];
    format(str, sizeof str, "%d", g_PlayerCount);
    TextDrawSetString(g_Banner, str);
}
