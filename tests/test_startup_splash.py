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


def test_startup_splash_prioritizes_brand_text_on_narrow_width(qapp) -> None:
    splash = StartupSplash(AppLanguage.EN)
    splash.setFixedSize(650, 410)
    splash.show()
    qapp.processEvents()

    assert not splash.rig.isVisible()
    assert splash.product_label.text() == "DIGITAL GEOLOG"
    assert splash.suite_label.text() == "GASRATIO&PIXLER"
    assert splash.product_label.width() >= splash.product_label.sizeHint().width()
    assert splash.suite_label.width() >= splash.suite_label.sizeHint().width()

    splash.close()
