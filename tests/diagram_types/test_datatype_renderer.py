"""Renderer tests for the datatype diagram type (restricted UML class diagram).

Covers: all five classifier_kinds, attribute compartment, enumeration literals,
all five dt-* connection arrows, src/tgt cardinality labels, variant+generalization_set
data tolerance, and collect_references binding extraction.
"""

from __future__ import annotations

from pathlib import Path

from src.diagram_types.datatype.renderer import DatatypePumlRenderer

_REPO = Path("/fake/root")


def _renderer() -> DatatypePumlRenderer:
    return DatatypePumlRenderer({})


def _render(*, classifiers=None, connections=None) -> str:
    return _renderer().render_body(
        "Test Diagram",
        [],
        [],
        "datatype",
        _REPO,
        diagram_entities={"classifier": classifiers or []},
        diagram_connections=connections or [],
    )


def _cls(cid, *, kind="class", label=None, **extra):
    d = {"id": cid, "classifier_kind": kind}
    if label:
        d["label"] = label
    d.update(extra)
    return d


# ---------------------------------------------------------------------------
# Classifier kinds
# ---------------------------------------------------------------------------


class TestClassifierKinds:
    def test_class_uses_class_keyword(self):
        out = _render(classifiers=[_cls("c1", label="Order")])
        assert 'class "Order"' in out

    def test_datatype_has_stereotype(self):
        out = _render(classifiers=[_cls("c1", kind="datatype", label="Money")])
        assert "<<datatype>>" in out
        assert 'class "Money"' in out

    def test_enumeration_uses_enum_keyword(self):
        out = _render(classifiers=[_cls("c1", kind="enumeration", label="Status")])
        assert 'enum "Status"' in out

    def test_variant_uses_abstract_class(self):
        out = _render(classifiers=[_cls("c1", kind="variant", label="Shape")])
        assert "abstract class" in out
        assert "<<variant>>" in out

    def test_primitive_has_stereotype(self):
        out = _render(classifiers=[_cls("c1", kind="primitive", label="String")])
        assert "<<primitive>>" in out

    def test_alias_derived_from_id(self):
        out = _render(classifiers=[_cls("DOB@123.abc")])
        assert "as _DOB_123_abc" in out


# ---------------------------------------------------------------------------
# Attribute compartment
# ---------------------------------------------------------------------------


class TestAttributes:
    def _attr(self, **kwargs):
        return {"name": "field", "type": "string", **kwargs}

    def test_attribute_name_present(self):
        out = _render(classifiers=[_cls("c1", attributes=[{"name": "price", "type": "decimal"}])])
        assert "price" in out
        assert "decimal" in out

    def test_attribute_multiplicity_present(self):
        out = _render(classifiers=[_cls("c1", attributes=[{
            "name": "tags", "type": "string", "multiplicity": "0..*"
        }])])
        assert "[0..*]" in out

    def test_attribute_is_id_marker(self):
        out = _render(classifiers=[_cls("c1", attributes=[{
            "name": "id", "type": "uuid", "is_id": True
        }])])
        assert "{id}" in out

    def test_attribute_without_is_id_no_marker(self):
        out = _render(classifiers=[_cls("c1", attributes=[{"name": "name", "type": "string"}])])
        assert "{id}" not in out

    def test_attribute_unique_marker(self):
        out = _render(classifiers=[_cls("c1", attributes=[{
            "name": "email", "type": "string", "is_unique": True,
        }])])
        assert "{unique}" in out

    def test_composite_unique_constraint_note(self):
        out = _render(classifiers=[_cls(
            "c1",
            attributes=[{"name": "tenant"}, {"name": "number"}],
            unique_constraints=[["tenant", "number"]],
        )])
        assert "{unique(tenant, number)}" in out


# ---------------------------------------------------------------------------
# Enumeration literals
# ---------------------------------------------------------------------------


class TestLiterals:
    def test_literals_in_body(self):
        out = _render(classifiers=[_cls(
            "c1", kind="enumeration", label="Color",
            literals=["RED", "GREEN", "BLUE"],
        )])
        assert "RED" in out
        assert "GREEN" in out
        assert "BLUE" in out

    def test_literals_not_rendered_for_class_kind(self):
        out = _render(classifiers=[_cls(
            "c1", kind="class",
            literals=["GHOST"],
        )])
        assert "GHOST" not in out


# ---------------------------------------------------------------------------
# dt-* connection arrows
# ---------------------------------------------------------------------------


class TestConnectionArrows:
    def _conn(self, conn_type):
        return {"id": "e1", "source": "a", "target": "b", "conn_type": conn_type}

    def test_dt_association_arrow(self):
        out = _render(connections=[self._conn("dt-association")])
        assert " -- " in out

    def test_dt_aggregation_arrow(self):
        out = _render(connections=[self._conn("dt-aggregation")])
        assert "o--" in out

    def test_dt_composition_arrow(self):
        out = _render(connections=[self._conn("dt-composition")])
        assert "*--" in out

    def test_dt_generalization_arrow(self):
        out = _render(connections=[self._conn("dt-generalization")])
        assert "--|>" in out

    def test_dt_dependency_arrow(self):
        out = _render(connections=[self._conn("dt-dependency")])
        assert "..>" in out

    def test_unknown_conn_type_excluded(self):
        out = _render(connections=[{"id": "e1", "source": "a", "target": "b", "conn_type": "seq-from"}])
        assert "seq-from" not in out


# ---------------------------------------------------------------------------
# Cardinality labels
# ---------------------------------------------------------------------------


class TestCardinality:
    def test_tgt_cardinality_in_output(self):
        out = _render(connections=[{
            "id": "e1", "source": "a", "target": "b",
            "conn_type": "dt-association", "tgt_cardinality": "0..*",
        }])
        assert '"0..*"' in out

    def test_src_cardinality_in_output(self):
        out = _render(connections=[{
            "id": "e1", "source": "a", "target": "b",
            "conn_type": "dt-association", "src_cardinality": "1",
        }])
        assert '"1"' in out

    def test_connection_label_in_output(self):
        out = _render(connections=[{
            "id": "e1", "source": "a", "target": "b",
            "conn_type": "dt-association", "label": "owns",
        }])
        assert ": owns" in out


class TestNotes:
    def test_classifier_note_in_output(self):
        out = _render(classifiers=[_cls("c1", label="Order", note="Aggregate root")])
        assert "note right of _c1" in out
        assert "Aggregate root" in out

    def test_connection_note_in_output(self):
        out = _render(connections=[{
            "id": "e1",
            "source": "a",
            "target": "b",
            "conn_type": "dt-association",
            "note": "Derived relation",
        }])
        assert "note on link" in out
        assert "Derived relation" in out


# ---------------------------------------------------------------------------
# Variant + generalization_set tolerance
# ---------------------------------------------------------------------------


class TestVariantGeneralizationSet:
    def test_variant_with_generalization_set_does_not_crash(self):
        out = _render(classifiers=[_cls(
            "c1", kind="variant", label="Shape",
            generalization_set={"is_covering": True, "is_disjoint": True},
        )])
        assert "abstract class" in out

    def test_variant_without_generalization_set_renders_cleanly(self):
        out = _render(classifiers=[_cls("c1", kind="variant", label="Shape")])
        assert "abstract class" in out
        assert "@startuml" in out
        assert "@enduml" in out


# ---------------------------------------------------------------------------
# collect_references
# ---------------------------------------------------------------------------


class TestCollectReferences:
    def _bindings(self, entity_ids=(), conn_ids=()):
        result = []
        for eid in entity_ids:
            result.append({"id": f"b_{eid}", "target": {"entity_id": eid}})
        for cid in conn_ids:
            result.append({"id": f"b_{cid}", "target": {"connection_id": cid}})
        return result

    def test_entity_ids_extracted_from_bindings(self):
        refs = _renderer().collect_references(
            "datatype", _REPO,
            bindings=self._bindings(entity_ids=["DOB@1.abc", "DOB@2.def"]),
        )
        assert "DOB@1.abc" in refs.entity_ids
        assert "DOB@2.def" in refs.entity_ids

    def test_connection_ids_extracted_from_bindings(self):
        refs = _renderer().collect_references(
            "datatype", _REPO,
            bindings=self._bindings(conn_ids=["DOB@1---DOB@2@@archimate-association"]),
        )
        assert "DOB@1---DOB@2@@archimate-association" in refs.connection_ids

    def test_empty_bindings_returns_empty_refs(self):
        refs = _renderer().collect_references("datatype", _REPO, bindings=[])
        assert refs.entity_ids == ()
        assert refs.connection_ids == ()

    def test_no_duplicates_in_entity_ids(self):
        bindings = self._bindings(entity_ids=["DOB@1.abc"]) * 2
        refs = _renderer().collect_references("datatype", _REPO, bindings=bindings)
        assert refs.entity_ids.count("DOB@1.abc") == 1
