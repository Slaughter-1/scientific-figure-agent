"""Line-by-line port of ``mxGraphView.prototype.getPoint`` for the edge-label case.

This module is deliberately a *transcription* of the upstream JavaScript rather
than a re-derivation, so it can serve as an independent oracle for the encoder in
``figure_agent.backends.drawio_backend``. It must not import or reuse any of the
encoder's expressions.

Source: jgraph/mxgraph, ``javascript/src/js/view/mxGraphView.js``,
``mxGraphView.prototype.getPoint`` (upstream ``master``)::

    var gx = (geometry != null) ? geometry.x / 2 : 0;
    var pointCount = state.absolutePoints.length;
    var dist = Math.round((gx + 0.5) * state.length);
    var segment = state.segments[0];
    var length = 0;
    var index = 1;

    while (dist >= Math.round(length + segment) && index < pointCount - 1)
    {
        length += segment;
        segment = state.segments[index++];
    }

    var factor = (segment == 0) ? 0 : (dist - length) / segment;
    var p0 = state.absolutePoints[index-1];
    var pe = state.absolutePoints[index];
    ...
    var dx = pe.x - p0.x;
    var dy = pe.y - p0.y;
    var nx = (segment == 0) ? 0 : dy / segment;
    var ny = (segment == 0) ? 0 : dx / segment;

    x = p0.x + dx * factor + (nx * gy + offsetX) * this.scale;
    y = p0.y + dy * factor - (ny * gy - offsetY) * this.scale;

Two properties of that code are what this oracle exists to pin down:

* the normal applied to ``geometry.y`` is ``(dy/segment, -dx/segment)``, i.e.
  ``(+uy, -ux)`` in screen coordinates -- *not* ``(-uy, +ux)``;
* ``dist`` is rounded to a whole number *before* the segment-selection loop, and
  the loop compares against ``Math.round(length + segment)``.
"""

from __future__ import annotations

import math

Point = tuple[float, float]

__all__ = ["js_round", "segments_of", "get_point"]


def js_round(value: float) -> float:
    """``Math.round`` semantics: exact halves go towards +Infinity."""
    return math.floor(value + 0.5)


def segments_of(absolute_points: list[Point]) -> tuple[list[float], float]:
    """Reproduce ``mxCellState.segments`` and ``mxCellState.length``.

    ``mxCellState.prototype.updateCachedBounds`` stores the euclidean length of
    every consecutive pair of ``absolutePoints`` in ``segments`` and their sum in
    ``length``.
    """
    segments = [
        math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)
        for a, b in zip(absolute_points, absolute_points[1:])
    ]
    return segments, sum(segments)


def get_point(absolute_points: list[Point],
              geometry_x: float,
              geometry_y: float,
              offset: Point | None = None,
              scale: float = 1.0) -> Point:
    """Return the absolute label point mxGraph places for a relative geometry."""
    segments, total_length = segments_of(absolute_points)
    if not segments:
        raise ValueError("an edge state needs at least two absolute points")

    gx = geometry_x / 2
    point_count = len(absolute_points)
    dist = js_round((gx + 0.5) * total_length)
    segment = segments[0]
    length = 0.0
    index = 1

    while dist >= js_round(length + segment) and index < point_count - 1:
        length += segment
        segment = segments[index]
        index += 1

    factor = 0.0 if segment == 0 else (dist - length) / segment
    p0 = absolute_points[index - 1]
    pe = absolute_points[index]

    offset_x, offset_y = offset if offset is not None else (0.0, 0.0)
    dx = pe[0] - p0[0]
    dy = pe[1] - p0[1]
    nx = 0.0 if segment == 0 else dy / segment
    ny = 0.0 if segment == 0 else dx / segment

    x = p0[0] + dx * factor + (nx * geometry_y + offset_x) * scale
    y = p0[1] + dy * factor - (ny * geometry_y - offset_y) * scale
    return (x, y)
