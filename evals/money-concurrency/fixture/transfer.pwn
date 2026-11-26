// current /transfer: two statements, no transaction
CMD:transfer(playerid, params[])
{
    new targetid, amount;
    if (sscanf(params, "ud", targetid, amount)) return SendClientMessage(playerid, -1, "USAGE: /transfer <id> <amount>");
    if (amount <= 0) return 1;

    new query[160];
    mysql_format(g_DB, query, sizeof query, "UPDATE accounts SET balance = balance - %d WHERE id = %d", amount, PlayerRow(playerid));
    mysql_tquery(g_DB, query);

    mysql_format(g_DB, query, sizeof query, "UPDATE accounts SET balance = balance + %d WHERE id = %d", amount, PlayerRow(targetid));
    mysql_tquery(g_DB, query);

    SendClientMessage(playerid, -1, "Sent.");
    return 1;
}
