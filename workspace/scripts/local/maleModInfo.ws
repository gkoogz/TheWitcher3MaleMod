// Authored adapter diagnostic. No stock character, inventory or save mutations.
exec function MaleModInfo()
{
    theGame.GetGuiManager().ShowUserDialogAdv(
        90260930,
        "MaleMod",
        "The Witcher adapter is loaded. Fitted anatomy and live body controls are under development.",
        false,
        UDB_Ok
    );
}
