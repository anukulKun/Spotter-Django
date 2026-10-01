from rest_framework.renderers import JSONRenderer
class PrettyJSONRenderer(JSONRenderer):
    def get_indent(self, accepted_media_type, renderer_context):
        request=renderer_context.get('request')
        return 2 if request is not None and request.query_params.get('pretty') == '1' else None
