"""Constants for the Logical Entity integration.

See docs/PLAT-125-hardware-role-abstraction-design.md (gitops repository,
merge commit af668725e9c632b12ba9c7dfc7c4e83df631250c) for the accepted
design this integration implements a bounded spike of. That design and its
history use the original "Entity Role" naming; PLAT-220 renamed the product
concept to "Logical Entity" without changing the underlying behavior it
describes — see docs/PLAT-220-rename-to-logical-entity.md for the mapping.
"""

from __future__ import annotations

DOMAIN = "logical_entity"

# Logical entity record fields, shared by both configuration sources (config
# entry options and YAML) per design §6.1 — every field below means the same
# thing regardless of which source produced it.
CONF_LOGICAL_ID = "logical_id"
CONF_DOMAIN = "domain"
CONF_SOURCE = "source"
CONF_NAME = "name"
CONF_HIDE_SOURCE = "hide_source"
CONF_CAPABILITY_CONTRACT = "capability_contract"
CONF_DEVICE_CLASS = "device_class"

# Domains covered by this spike (design §1, §11): light prioritized, plus
# enough switch/binary_sensor coverage to validate the shared architecture.
DOMAIN_LIGHT = "light"
DOMAIN_SWITCH = "switch"
DOMAIN_BINARY_SENSOR = "binary_sensor"
SUPPORTED_DOMAINS = [DOMAIN_LIGHT, DOMAIN_SWITCH, DOMAIN_BINARY_SENSOR]

DEFAULT_HIDE_SOURCE = True

SERVICE_RELOAD = "reload"

CONFIG_ENTRY_VERSION = 1
YAML_SCHEMA_VERSION = 1

# Repair issue raised when a logical entity's source is removed from the
# registry (design §8): the logical entity survives, goes unavailable, and
# this issue deep-links the user back into the replace-hardware options
# step. Two distinct translation keys, not one: hassfest's strings.json
# schema treats a plain `description` and a `fix_flow` as mutually exclusive
# within one issue entry ("two or more values in the same group of
# exclusion 'fixable'", confirmed directly by this pass's own first CI
# run) — a real in-tree fixable issue (e.g. workday's `bad_country`)
# carries only `title` + `fix_flow`, no top-level `description`. A
# UI-owned logical entity's issue (`ISSUE_UNBOUND_FIXABLE`, is_fixable=True,
# entry_id known — repairs.py) and a YAML-owned logical entity's issue
# (`ISSUE_UNBOUND`, is_fixable=False, no config entry to deep-link into) are
# therefore two different translation keys sharing the same
# {logical_entity_name}/{entity_id} placeholders, chosen at creation time in
# entity.py::_handle_source_unbound by whether entry_id is available — not
# one key trying to serve both display shapes.
ISSUE_UNBOUND = "logical_entity_unbound"
ISSUE_UNBOUND_FIXABLE = "logical_entity_unbound_fixable"
# Raised for a syntax-valid YAML file containing one invalid record (design
# §10.1 R7 / spike gate d): the file as a whole is not rejected, only the
# broken logical entity is flagged.
ISSUE_YAML_RECORD_INVALID = "yaml_record_invalid"

# hass.data storage keys.
DATA_LOGICAL_ENTITIES = "logical_entities"  # logical_id -> LogicalEntity, populated as entities register
DATA_FORWARD_CHAINS = "forward_chains"  # context.id -> set[logical_id], cycle guard (R3)
DATA_YAML_LOGICAL_ENTITIES = "yaml_logical_entities"  # logical_id -> record, last-reconciled YAML state
