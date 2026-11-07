"""Reject nonfinite derived quantities even when every input is finite."""

from __future__ import annotations

from dataclasses import replace

import pytest

from pvstring.calc import evaluate
from pvstring.library import load_builtin
from pvstring.models import Array, InputError, Site


@pytest.mark.parametrize("isc,parallel,fuse", [(1.3e308, 1, 25), (1e307, 1000, None)])
def test_derived_fuse_and_parallel_current_overflow(isc, parallel, fuse):
    module = replace(load_builtin("module", "generic-410"),
                     isc=isc, imp=1, pmax_stc=31.4, alpha_isc=0)
    inverter = load_builtin("inverter", "generic-5kw")
    site = Site("Finite extreme test", tmin=0, thigh=25,
                fixed_delta_t=0, typical_cell_temperature=25)
    with pytest.raises(InputError, match="finite number"):
        evaluate(module, inverter, site, Array(8, (parallel, 0), fuse))
