"""Never overwrite an existing optional credential with a disabled placeholder."""
def should_replace(credential_id,has_replacement,existing_ids):
 return credential_id not in existing_ids or bool(has_replacement)
