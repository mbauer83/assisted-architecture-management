
from dataclasses import dataclass
from typing import Literal


DiagramConnectionInferenceMode = Literal["none", "auto", "strict"]

# 2026-04-15: EntityTypeInfo and ConnectionTypeInfo should be commonly used data-structures. Currently entity- and connection-info is duplicated and non-centralized (archimate_types.py, connection_ontology.py, model_write_catalog.py etc.)
# EntityTypeInfo Needs additional info about entity class ([internal / external] [passive / active] structure element, [internal / external] behavior element).
# Connection-restrictions (based on connection_ontology.py) can be specified in terms of predicates on 3-tuples of ([SOURCE], [RELATION], [TARGET]) where [SOURCE] and [TARGET] can be elements, connections or junctions.
@dataclass(frozen=True)
class EntityTypeInfo:
    artifact_type: str
    prefix: str
    domain_dir: str
    subdir: str
    archimate_domain: str
    archimate_element_type: str


@dataclass(frozen=True)
class ConnectionTypeInfo:
    artifact_type: str
    conn_lang: str
    conn_dir: str
    archimate_relationship_type: str | None = None


ENTITY_TYPES: dict[str, EntityTypeInfo] = {
    "stakeholder": EntityTypeInfo("stakeholder", "STK", "motivation", "stakeholders", "Motivation", "Stakeholder"),
    "driver": EntityTypeInfo("driver", "DRV", "motivation", "drivers", "Motivation", "Driver"),
    "assessment": EntityTypeInfo("assessment", "ASS", "motivation", "assessments", "Motivation", "Assessment"),
    "goal": EntityTypeInfo("goal", "GOL", "motivation", "goals", "Motivation", "Goal"),
    "outcome": EntityTypeInfo("outcome", "OUT", "motivation", "outcomes", "Motivation", "Outcome"),
    "principle": EntityTypeInfo("principle", "PRI", "motivation", "principles", "Motivation", "Principle"),
    "requirement": EntityTypeInfo("requirement", "REQ", "motivation", "requirements", "Motivation", "Requirement"),
    "architecture-constraint": EntityTypeInfo("architecture-constraint", "CST", "motivation", "constraints", "Motivation", "Constraint"),
    "meaning": EntityTypeInfo("meaning", "MEA", "motivation", "meanings", "Motivation", "Meaning"),
    "value": EntityTypeInfo("value", "VAL", "motivation", "values", "Motivation", "Value"),
    "capability": EntityTypeInfo("capability", "CAP", "strategy", "capabilities", "Strategy", "Capability"),
    "value-stream": EntityTypeInfo("value-stream", "VS", "strategy", "value-streams", "Strategy", "ValueStream"),
    "resource": EntityTypeInfo("resource", "RES", "strategy", "resources", "Strategy", "Resource"),
    "course-of-action": EntityTypeInfo("course-of-action", "COA", "strategy", "courses-of-action", "Strategy", "CourseOfAction"),
    # Common domain — domain-neutral behavioral elements (ArchiMate NEXT)
    "service": EntityTypeInfo("service", "SRV", "common", "services", "Common", "Service"),
    "process": EntityTypeInfo("process", "PRC", "common", "processes", "Common", "Process"),
    "function": EntityTypeInfo("function", "FNC", "common", "functions", "Common", "Function"),
    "interaction": EntityTypeInfo("interaction", "INT", "common", "interactions", "Common", "Interaction"),
    "event": EntityTypeInfo("event", "EVT", "common", "events", "Common", "Event"),
    "role": EntityTypeInfo("role", "ROL", "common", "roles", "Common", "Role"),
    "business-actor": EntityTypeInfo("business-actor", "ACT", "business", "actors", "Business", "BusinessActor"),
    "business-interface": EntityTypeInfo("business-interface", "BIF", "business", "interfaces", "Business", "BusinessInterface"),
    "business-object": EntityTypeInfo("business-object", "BOB", "business", "objects", "Business", "BusinessObject"),
    "contract": EntityTypeInfo("contract", "CTR", "business", "contracts", "Business", "Contract"),
    "product": EntityTypeInfo("product", "PRD", "business", "products", "Business", "Product"),
    "application-component": EntityTypeInfo("application-component", "APP", "application", "components", "Application", "ApplicationComponent"),
    "application-interface": EntityTypeInfo("application-interface", "AIF", "application", "interfaces", "Application", "ApplicationInterface"),
    "data-object": EntityTypeInfo("data-object", "DOB", "application", "data-objects", "Application", "DataObject"),
    "technology-node": EntityTypeInfo("technology-node", "NOD", "technology", "nodes", "Technology", "Node"),
    "device": EntityTypeInfo("device", "DEV", "technology", "devices", "Technology", "Device"),
    "system-software": EntityTypeInfo("system-software", "SSW", "technology", "system-software", "Technology", "SystemSoftware"),
    "technology-interface": EntityTypeInfo("technology-interface", "TIF", "technology", "interfaces", "Technology", "TechnologyInterface"),
    "path": EntityTypeInfo("path", "PTH", "technology", "paths", "Technology", "Path"),
    "communication-network": EntityTypeInfo("communication-network", "NET", "technology", "networks", "Technology", "CommunicationNetwork"),
    "artifact": EntityTypeInfo("artifact", "ART", "technology", "artifacts", "Technology", "Artifact"),
    "equipment": EntityTypeInfo("equipment", "EQP", "technology", "equipment", "Technology", "Equipment"),
    "facility": EntityTypeInfo("facility", "FAC", "technology", "facilities", "Technology", "Facility"),
    "distribution-network": EntityTypeInfo("distribution-network", "DIS", "technology", "distribution-networks", "Technology", "DistributionNetwork"),
    "material": EntityTypeInfo("material", "MAT", "technology", "materials", "Technology", "Material"),
    "work-package": EntityTypeInfo("work-package", "WP", "implementation", "work-packages", "Implementation", "WorkPackage"),
    "deliverable": EntityTypeInfo("deliverable", "DEL", "implementation", "deliverables", "Implementation", "Deliverable"),
    "implementation-event": EntityTypeInfo("implementation-event", "IEV", "implementation", "events", "Implementation", "ImplementationEvent"),
    "plateau": EntityTypeInfo("plateau", "PLT", "implementation", "plateaus", "Implementation", "Plateau"),
}


CONNECTION_TYPES: dict[str, ConnectionTypeInfo] = {
    "archimate-composition": ConnectionTypeInfo("archimate-composition", "archimate", "composition", "Composition"),
    "archimate-aggregation": ConnectionTypeInfo("archimate-aggregation", "archimate", "aggregation", "Aggregation"),
    "archimate-assignment": ConnectionTypeInfo("archimate-assignment", "archimate", "assignment", "Assignment"),
    "archimate-realization": ConnectionTypeInfo("archimate-realization", "archimate", "realization", "Realization"),
    "archimate-serving": ConnectionTypeInfo("archimate-serving", "archimate", "serving", "Serving"),
    "archimate-access": ConnectionTypeInfo("archimate-access", "archimate", "access", "Access"),
    "archimate-influence": ConnectionTypeInfo("archimate-influence", "archimate", "influence", "Influence"),
    "archimate-association": ConnectionTypeInfo("archimate-association", "archimate", "association", "Association"),
    "archimate-specialization": ConnectionTypeInfo("archimate-specialization", "archimate", "specialization", "Specialization"),
    "archimate-flow": ConnectionTypeInfo("archimate-flow", "archimate", "flow", "Flow"),
    "archimate-triggering": ConnectionTypeInfo("archimate-triggering", "archimate", "triggering", "Triggering"),
    "er-one-to-many": ConnectionTypeInfo("er-one-to-many", "er", "one-to-many"),
    "er-many-to-many": ConnectionTypeInfo("er-many-to-many", "er", "many-to-many"),
    "er-one-to-one": ConnectionTypeInfo("er-one-to-one", "er", "one-to-one"),
    "sequence-synchronous": ConnectionTypeInfo("sequence-synchronous", "sequence", "synchronous"),
    "sequence-asynchronous": ConnectionTypeInfo("sequence-asynchronous", "sequence", "asynchronous"),
    "sequence-return": ConnectionTypeInfo("sequence-return", "sequence", "return"),
    "sequence-create": ConnectionTypeInfo("sequence-create", "sequence", "create"),
    "sequence-destroy": ConnectionTypeInfo("sequence-destroy", "sequence", "destroy"),
    "activity-sequence-flow": ConnectionTypeInfo("activity-sequence-flow", "activity", "sequence-flow"),
    "activity-decision": ConnectionTypeInfo("activity-decision", "activity", "decision"),
    "activity-message-flow": ConnectionTypeInfo("activity-message-flow", "activity", "message-flow"),
    "activity-data-association": ConnectionTypeInfo("activity-data-association", "activity", "data-association"),
    "usecase-include": ConnectionTypeInfo("usecase-include", "usecase", "include"),
    "usecase-extend": ConnectionTypeInfo("usecase-extend", "usecase", "extend"),
    "usecase-association": ConnectionTypeInfo("usecase-association", "usecase", "actor-association"),
    "usecase-generalization": ConnectionTypeInfo("usecase-generalization", "usecase", "generalization"),
}


ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE: dict[str, str] = {
    "composition": "archimate-composition",
    "aggregation": "archimate-aggregation",
    "assignment": "archimate-assignment",
    "realization": "archimate-realization",
    "serving": "archimate-serving",
    "access": "archimate-access",
    "influence": "archimate-influence",
    "association": "archimate-association",
    "specialization": "archimate-specialization",
    "flow": "archimate-flow",
    "triggering": "archimate-triggering",
}
