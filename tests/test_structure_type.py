from core.structure_type import StructureType


def test_structure_type_values():

    assert StructureType.HH.value == "HH"
    assert StructureType.HL.value == "HL"
    assert StructureType.LH.value == "LH"
    assert StructureType.LL.value == "LL"