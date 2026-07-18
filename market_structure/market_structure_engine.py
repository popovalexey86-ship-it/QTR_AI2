from core.market_structure_state import MarketStructureState
from core.structure import Structure
from core.structure_type import StructureType


class MarketStructureEngine:

    def update(
        self,
        state: MarketStructureState,
        structures: list[Structure],
    ) -> None:

        for structure in structures:

            match structure.type:

                case StructureType.HH:
                    state.previous_hh = state.last_hh
                    state.last_hh = structure

                case StructureType.HL:
                    state.previous_hl = state.last_hl
                    state.last_hl = structure

                case StructureType.LH:
                    state.previous_lh = state.last_lh
                    state.last_lh = structure

                case StructureType.LL:
                    state.previous_ll = state.last_ll
                    state.last_ll = structure