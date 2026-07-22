from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.drilling_animation import DrillingAnimation
from geoworkbench.ui.startup_splash import StartupSplash


def test_startup_splash_is_branded_animated_and_screen_safe(qapp) -> None:
    splash = StartupSplash(AppLanguage.EN)
    splash.show()
    qapp.processEvents()

    screen = splash.screen()
    assert screen is not None
    assert screen.availableGeometry().contains(splash.geometry())
    assert splash.findChild(DrillingAnimation, "splashRig") is splash.rig
    assert "Preparing" in splash.stage_label.text()

    splash.set_stage("Loading test", 64)
    assert splash.stage_label.text() == "Loading test"
    assert splash.progress.value() == 64
    assert not splash.grab().isNull()

    splash.finish()
    assert splash.progress.value() == 100
    splash.close()
