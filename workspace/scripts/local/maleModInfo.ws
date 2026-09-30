// Authored adapter diagnostic. No stock character, inventory or save mutations.
exec function MaleModInfo()
{
    theGame.GetGuiManager().ShowUserDialogAdv(
        90260930,
        "MaleMod",
        "MaleMod 0.3 anatomy test. The fitted model follows Geralt's rig. Live size controls and secondary motion are still under development.",
        false,
        UDB_Ok
    );
}
