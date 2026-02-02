"""
Animation system for the PySide6 shell.

Replaces Fabric's Revealer + CSS transitions with Qt property animations.
All durations and easing curves match the existing Fabric implementation.

Primary curve: cubic-bezier(0.175, 0.885, 0.32, 1.275) — spring with overshoot
Primary duration: 250ms
"""

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve, QParallelAnimationGroup, QPoint, QPointF,
    QPropertyAnimation, QSequentialAnimationGroup, QSize, Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect, QStackedWidget, QWidget,
)


def _make_spring_curve() -> QEasingCurve:
    """cubic-bezier(0.175, 0.885, 0.32, 1.275) — spring with overshoot."""
    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(
        QPointF(0.175, 0.885),
        QPointF(0.32, 1.275),
        QPointF(1.0, 1.0),
    )
    return curve


def _make_smooth_curve() -> QEasingCurve:
    """cubic-bezier(0.175, 0.885, 0.32, 1) — no overshoot."""
    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(
        QPointF(0.175, 0.885),
        QPointF(0.32, 1.0),
        QPointF(1.0, 1.0),
    )
    return curve


SPRING = _make_spring_curve()
SMOOTH = _make_smooth_curve()
EASE = QEasingCurve(QEasingCurve.Type.InOutQuad)


def _ensure_opacity_effect(widget: QWidget) -> QGraphicsOpacityEffect:
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    return effect


class Animator:
    """Static factory for common shell animations.

    All methods return a QPropertyAnimation (or group) that the caller
    must keep a reference to (or connect finished to deleteLater).
    """

    @staticmethod
    def fade(
        widget: QWidget,
        start: float = 0.0,
        end: float = 1.0,
        duration: int = 250,
        curve: QEasingCurve = SPRING,
    ) -> QPropertyAnimation:
        effect = _ensure_opacity_effect(widget)
        effect.setOpacity(start)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setDuration(duration)
        anim.setEasingCurve(curve)
        return anim

    @staticmethod
    def slide(
        widget: QWidget,
        direction: str,
        distance: int = 0,
        duration: int = 250,
        curve: QEasingCurve = SPRING,
        reverse: bool = False,
    ) -> QPropertyAnimation:
        """Slide widget in from a direction.

        direction: "up", "down", "left", "right"
        distance: pixels to slide (0 = auto from widget size)
        reverse: True = slide out instead of in
        """
        if distance == 0:
            if direction in ("up", "down"):
                distance = widget.height() or 100
            else:
                distance = widget.width() or 200

        offsets = {
            "up": QPoint(0, -distance),
            "down": QPoint(0, distance),
            "left": QPoint(-distance, 0),
            "right": QPoint(distance, 0),
        }
        offset = offsets.get(direction, QPoint(0, 0))
        origin = widget.pos()

        anim = QPropertyAnimation(widget, b"pos")
        if reverse:
            anim.setStartValue(origin)
            anim.setEndValue(origin + offset)
        else:
            anim.setStartValue(origin + offset)
            anim.setEndValue(origin)
        anim.setDuration(duration)
        anim.setEasingCurve(curve)
        return anim

    @staticmethod
    def resize(
        widget: QWidget,
        start_size: QSize,
        end_size: QSize,
        duration: int = 250,
        curve: QEasingCurve = SPRING,
    ) -> QPropertyAnimation:
        anim = QPropertyAnimation(widget, b"size")
        anim.setStartValue(start_size)
        anim.setEndValue(end_size)
        anim.setDuration(duration)
        anim.setEasingCurve(curve)
        return anim

    @staticmethod
    def group(
        *animations: QPropertyAnimation,
        parallel: bool = True,
    ) -> QParallelAnimationGroup | QSequentialAnimationGroup:
        if parallel:
            grp = QParallelAnimationGroup()
        else:
            grp = QSequentialAnimationGroup()
        for anim in animations:
            grp.addAnimation(anim)
        return grp


class AnimatedStack(QStackedWidget):
    """QStackedWidget with animated transitions between pages.

    Replaces Fabric's Stack with transition_type="crossfade" / "slide-*".
    """

    transition_finished = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._transition_duration = 250
        self._transition_type = "crossfade"
        self._animating = False
        self._active_anim = None  # prevent GC

    @property
    def transition_duration(self) -> int:
        return self._transition_duration

    @transition_duration.setter
    def transition_duration(self, value: int):
        self._transition_duration = value

    @property
    def transition_type(self) -> str:
        return self._transition_type

    @transition_type.setter
    def transition_type(self, value: str):
        self._transition_type = value

    def switch_to(
        self,
        index: int,
        transition: Optional[str] = None,
        duration: Optional[int] = None,
    ):
        if self._animating:
            return
        if index == self.currentIndex():
            self.transition_finished.emit(index)
            return

        transition = transition or self._transition_type
        duration = duration or self._transition_duration

        if transition == "crossfade":
            self._crossfade_to(index, duration)
        elif transition and transition.startswith("slide-"):
            direction = transition.split("-", 1)[1]
            self._slide_to(index, direction, duration)
        else:
            self.setCurrentIndex(index)
            self.transition_finished.emit(index)

    def _crossfade_to(self, index: int, duration: int):
        self._animating = True
        old_widget = self.currentWidget()
        new_widget = self.widget(index)

        if not old_widget or not new_widget:
            self.setCurrentIndex(index)
            self._animating = False
            self.transition_finished.emit(index)
            return

        half = duration // 2

        fade_out = Animator.fade(old_widget, 1.0, 0.0, half, SMOOTH)

        def on_fade_out_done():
            # Reset old widget opacity
            effect = old_widget.graphicsEffect()
            if isinstance(effect, QGraphicsOpacityEffect):
                effect.setOpacity(1.0)

            self.setCurrentIndex(index)

            fade_in = Animator.fade(new_widget, 0.0, 1.0, half, SMOOTH)
            fade_in.finished.connect(lambda: self._finish_transition(index))
            self._active_anim = fade_in
            fade_in.start()

        fade_out.finished.connect(on_fade_out_done)
        self._active_anim = fade_out
        fade_out.start()

    def _slide_to(self, index: int, direction: str, duration: int):
        self._animating = True
        new_widget = self.widget(index)

        if not new_widget:
            self.setCurrentIndex(index)
            self._animating = False
            self.transition_finished.emit(index)
            return

        self.setCurrentIndex(index)
        anim = Animator.slide(new_widget, direction, duration=duration)
        anim.finished.connect(lambda: self._finish_transition(index))
        self._active_anim = anim
        anim.start()

    def _finish_transition(self, index: int):
        self._animating = False
        self._active_anim = None
        self.transition_finished.emit(index)
