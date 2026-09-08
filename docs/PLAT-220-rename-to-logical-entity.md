# PLAT-220: rename Entity Role → Logical Entity

## Objective

Rename the integration previously developed as `home-assistant-entity-role` /
`entity_role` to **Logical Entity** / `logical_entity`, so the name matches what the
integration actually provides: a stable logical entity bound to a replaceable physical/source
entity. This is a pure nomenclature change — the underlying behavior, architecture, and test
coverage carried over from `home-assistant-entity-role` (PLAT-125/126/128/130) are unchanged.

## Why

`entity_role` was misleading. The integration does not classify semantic roles such as
`primary_light` or `accent_light`; it creates a stable logical endpoint whose source can be
rebound without changing the identity used by automations, scenes, and dashboards. **Role** is
reserved going forward for a possible future semantic-classification layer (e.g.
`primary_light`, `accent_light`, `video_light`, `equipment_power`) that does not exist yet — see
[Non-goal](#non-goal-a-future-role-layer) below.

## Terminology mapping

| Old (`home-assistant-entity-role`)                  | New (`home-assistant-logical-entity`)         |
| ---------------------------------------------------- | ---------------------------------------------- |
| repository/project `home-assistant-entity-role`      | `home-assistant-logical-entity`                |
| integration domain `entity_role`                     | `logical_entity`                               |
| `role_id`                                             | `logical_id`                                   |
| `role_domain`                                         | `domain`                                       |
| `source`                                              | unchanged                                      |
| `capability_contract`                                 | unchanged                                      |
| `hide_source`                                         | unchanged                                      |
| class `RoleEntity`                                    | `LogicalEntity`                                |
| classes `EntityRoleLight`/`Switch`/`BinarySensor`     | `LogicalEntityLight`/`Switch`/`BinarySensor`   |
| classes `EntityRoleConfigFlow`/`OptionsFlow`          | `LogicalEntityConfigFlow`/`OptionsFlow`        |
| `hass.data[DOMAIN]["roles"]`                          | `hass.data[DOMAIN]["logical_entities"]`        |
| `DATA_ROLES`/`DATA_YAML_ROLES`                        | `DATA_LOGICAL_ENTITIES`/`DATA_YAML_LOGICAL_ENTITIES` |
| `ROLE_SCHEMA`/`ROLE_LIST_SCHEMA`                      | `LOGICAL_ENTITY_SCHEMA`/`LOGICAL_ENTITY_LIST_SCHEMA` |
| issue keys `role_unbound`/`role_unbound_fixable`      | `logical_entity_unbound`/`logical_entity_unbound_fixable` |
| reason code `role_on_role_rejected`                   | `logical_entity_source_rejected`               |
| service `entity_role.reload`                          | `logical_entity.reload`                        |
| user-facing object "a role"                           | "a logical entity"                             |
| operation "bind/rebind role"                          | "bind/rebind logical entity"                   |

`yaml_record_invalid` (the third repair-issue key) and its `reason`/`logical_id`
translation placeholders keep their names; only the record-identity placeholder changed
(`role_id` → `logical_id`, per the table above).

## What moved, what didn't

- The full `custom_components/entity_role/` implementation was ported into
  `custom_components/logical_entity/` under the mapping above — every module, including
  `hide.py` (which never referenced "role" and needed no renaming beyond its own docstring
  cross-references to sibling modules).
- The test suite (`tests/`) was ported and renamed the same way, including test names and
  internal fixture/helper identifiers (e.g. `role_entity_id` → `entity_id_for_logical_entity`,
  `_setup_role` → `_setup_logical_entity`). `test_light_role.py` was renamed to `test_light.py`
  (the `_role` suffix no longer applies).
- `strings.json`/`translations/en.json`, `services.yaml`, `manifest.json`, and `hacs.json` were
  updated to the new domain/name/vocabulary.
- **`docs/PLAT-126-spike-results.md`, `docs/PLAT-128-production-results.md`, and
  `docs/PLAT-130-device-linkage-results.md` were carried over unmodified.** They are historical
  records of the spike/production passes as they actually happened, under the naming in use at
  the time (`entity_role`/`role_id`/"Entity Role") — rewriting them under the new terminology
  would misrepresent what those passes actually did and reviewed. This is the
  "historical/migration documentation intentionally mentions the old names" exception the
  rename ticket (PLAT-220) itself carves out.
- The authoritative architecture document, `PLAT-125-hardware-role-abstraction-design.md`
  (`platta/gitops`, merge commit `af668725e9c632b12ba9c7dfc7c4e83df631250c`), likewise still uses
  the original "Entity Role"/role-abstraction naming and file name — it is a frozen, accepted
  design document, and updating its prose is out of this rename ticket's scope. This document
  (`PLAT-220-rename-to-logical-entity.md`) is the authoritative mapping between that design's
  vocabulary and this repository's current code; a reader should treat every `role_id` in the
  design as `logical_id` here, every `role_domain` as `domain`, and every "role" (the stable
  indirection concept) as "logical entity", per the table above.
- The GitOps declarative configuration (`platta/gitops`) was updated in the same PLAT-220 pass —
  see that repository's own history for the corresponding change (new `logical_entity:` YAML
  path/schema, updated Home Assistant deployment wiring, and retirement of the
  `entity_role`/`entity-roles.yaml` path once the new integration was confirmed working).
- The original `home-assistant-entity-role` repository is expected to be retired once this
  integration is proven working in production (PLAT-220 item 10) — that removal is a follow-on
  step, not part of this rename commit, so as not to leave the production Home Assistant
  instance without a working integration mid-migration.

## Non-goal: a future "role" layer

Nothing here precludes a later, separate semantic-classification layer built *on top of*
logical entities — e.g. tagging a `light.kitchen_counter` logical entity as `primary_light` for
a room, independent of which physical device or even which logical entity currently backs that
tag. That hypothetical layer is what the word **role** is reserved for going forward. It does not
exist in this repository today; nothing in this rename should be read as already implementing it.
