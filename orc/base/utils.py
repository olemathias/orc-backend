STATUS = (
    ('pending', 'Pending'),
    ('waiting', 'Waiting'),
    ('provisioning', 'Provisioning'),
    ('provisioned', 'Provisioned'),
    ('error', 'Error'),
)

def get_tag_value(tags, tag, default = None):
    if tags is None:
        return default
    for item in tags:
        if item["key"].lower() == tag.lower():
            return item["value"]
    return default