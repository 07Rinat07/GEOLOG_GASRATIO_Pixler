"""Menu-free tablet PlotItem, adapted from pyqtgraph 0.14.0.

The tablet never exposes upstream Plot Options or ViewBox menus. Its normal
plot methods still require the original control widgets and signal wiring.
The upstream constructor unconditionally creates six QWidgetActions even
with enableMenu=False; Windows CI faulted at sm.addAction(act).

Adapted from pyqtgraph/graphicsItems/PlotItem/PlotItem.py (tag
pyqtgraph-0.14.0). Keep this adapter limited to the tablet, and review it
when upgrading pyqtgraph. The CurveView continues to use upstream PlotItem.

Copyright (c) 2012  University of North Carolina at Chapel Hill
Luke Campagnola    ('luke.campagnola@%s.com' % 'gmail')

The MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

from pyqtgraph import functions as fn, icons
from pyqtgraph.Qt import QtCore, QtWidgets
from pyqtgraph.WidgetGroup import WidgetGroup
from pyqtgraph.graphicsItems.ButtonItem import ButtonItem
from pyqtgraph.graphicsItems.GraphicsWidget import GraphicsWidget
from pyqtgraph.graphicsItems.LabelItem import LabelItem
from pyqtgraph.graphicsItems.PlotItem import PlotItem, plotConfigTemplate_generic as ui_template
from pyqtgraph.graphicsItems.ViewBox import ViewBox
import weakref

translate = QtCore.QCoreApplication.translate


class TabletPlotItem(PlotItem):
    """Retain upstream plotting controls without allocating any context menu."""

    def __init__(self, owner: QtWidgets.QWidget, axis_items: dict) -> None:
        GraphicsWidget.__init__(self)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )

        ## Set up control buttons
        self.autoBtn = ButtonItem(icons.getGraphPixmap('auto'), 14, self)
        self.autoBtn.mode = 'auto'
        self.autoBtn.clicked.connect(self.autoBtnClicked)
        self.buttonsHidden = False  # has the user has requested buttons to be hidden?
        self.mouseHovering = False

        self.layout = QtWidgets.QGraphicsGridLayout()
        self.layout.setContentsMargins(1,1,1,1)
        self.setLayout(self.layout)
        self.layout.setHorizontalSpacing(0)
        self.layout.setVerticalSpacing(0)

        self.vb = ViewBox(parent=self, enableMenu=False)
        self.vb.sigStateChanged.connect(self.viewStateChanged)

        # Enable or disable plotItem menu
        self.setMenuEnabled(False, None)
        self.vb.sigRangeChanged.connect(self.sigRangeChanged)
        self.vb.sigXRangeChanged.connect(self.sigXRangeChanged)
        self.vb.sigYRangeChanged.connect(self.sigYRangeChanged)
        self.vb.sigRangeChangedManually.connect(self.sigRangeChangedManually)

        self.layout.addItem(self.vb, 2, 1)
        self.alpha = 1.0
        self.autoAlpha = True
        self.spectrumMode = False

        self.legend = None

        # Initialize axis items
        self.axes = {}
        self.setAxisItems(axis_items)

        self.titleLabel = LabelItem('', size='11pt', parent=self)
        self.layout.addItem(self.titleLabel, 0, 1)
        self.setTitle(None)  ## hide

        for i in range(4):
            self.layout.setRowPreferredHeight(i, 0)
            self.layout.setRowMinimumHeight(i, 0)
            self.layout.setRowSpacing(i, 0)
            self.layout.setRowStretchFactor(i, 1)

        for i in range(3):
            self.layout.setColumnPreferredWidth(i, 0)
            self.layout.setColumnMinimumWidth(i, 0)
            self.layout.setColumnSpacing(i, 0)
            self.layout.setColumnStretchFactor(i, 1)
        self.layout.setRowStretchFactor(2, 100)
        self.layout.setColumnStretchFactor(1, 100)


        self.items = []
        self.curves = []
        self.itemMeta = weakref.WeakKeyDictionary()
        self.dataItems = []
        self.paramList = {}
        self.avgCurves = {}
        # Change these properties to adjust the appearance of the averaged curve:
        self.avgPen = fn.mkPen((0, 200, 0))
        self.avgShadowPen = fn.mkPen((0, 0, 0), width=4)
        # Set up programmatic plot controls.
        # The controls still drive PlotItem methods (grid, log mode, etc.).
        # They stay in one ordinary, hidden QWidget tree owned by the track
        # until the actual PlotWidget is ready to take ownership.
        self.control_root = QtWidgets.QWidget(owner)
        self.control_root.hide()
        self.ctrl = c = ui_template.Ui_Form()
        c.setupUi(self.control_root)

        menuItems = [
            (translate("PlotItem", 'Transforms'), c.transformGroup),
            (translate("PlotItem", 'Downsample'), c.decimateGroup),
            (translate("PlotItem", 'Average'), c.averageGroup),
            (translate("PlotItem", 'Alpha'), c.alphaGroup),
            (translate("PlotItem", 'Grid'), c.gridGroup),
            (translate("PlotItem", 'Points'), c.pointsGroup),
        ]

        # Tablet has its own header context menu; never create native menu
        # actions for controls that cannot be opened by the operator.
        self.ctrlMenu = None

        self.stateGroup = WidgetGroup()
        for name, w in menuItems:
            self.stateGroup.autoAdd(w)

        self.fileDialog = None

        c.alphaGroup.toggled.connect(self.updateAlpha)
        c.alphaSlider.valueChanged.connect(self.updateAlpha)
        c.autoAlphaCheck.toggled.connect(self.updateAlpha)

        c.xGridCheck.toggled.connect(self.updateGrid)
        c.yGridCheck.toggled.connect(self.updateGrid)
        c.gridAlphaSlider.valueChanged.connect(self.updateGrid)

        c.fftCheck.toggled.connect(self.updateSpectrumMode)
        c.subtractMeanCheck.toggled.connect(self.updateSubtractMeanMode)
        c.logXCheck.toggled.connect(self.updateLogMode)
        c.logYCheck.toggled.connect(self.updateLogMode)
        c.derivativeCheck.toggled.connect(self.updateDerivativeMode)
        c.phasemapCheck.toggled.connect(self.updatePhasemapMode)

        c.downsampleSpin.valueChanged.connect(self.updateDownsampling)
        c.downsampleCheck.toggled.connect(self.updateDownsampling)
        c.autoDownsampleCheck.toggled.connect(self.updateDownsampling)
        c.subsampleRadio.toggled.connect(self.updateDownsampling)
        c.meanRadio.toggled.connect(self.updateDownsampling)
        c.clipToViewCheck.toggled.connect(self.updateDownsampling)

        self.ctrl.avgParamList.itemClicked.connect(self.avgParamListClicked)
        self.ctrl.averageGroup.toggled.connect(self.avgToggled)

        self.ctrl.maxTracesCheck.toggled.connect(self._handle_max_traces_toggle)
        self.ctrl.forgetTracesCheck.toggled.connect(self.updateDecimation)
        self.ctrl.maxTracesSpin.valueChanged.connect(self.updateDecimation)


    def close(self) -> None:
        # Match upstream scene/axis teardown, but use the actual ViewBox as
        # the idempotence sentinel: ctrlMenu is intentionally always None.
        if self.vb is None:
            return
        self.autoBtn.setParent(None)
        self.autoBtn = None
        for axis in self.axes.values():
            axis["item"].close()
        self.axes = None
        self.scene().removeItem(self.vb)
        self.vb = None
        # The hidden controls remain children of the plot until its native
        # QWidget tree is deleted, including when callers retain wrappers.
