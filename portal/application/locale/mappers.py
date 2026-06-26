"""
Map locale application results to API serializers.
"""
from portal.application.locale.results import LocaleListResult
from portal.serializers.admin.v1.locale import AdminLocaleItem, AdminLocaleList


def locale_list_result_to_api(result: LocaleListResult) -> AdminLocaleList:
    """
    Map locale list result to admin API response model.
    :param result:
    :return:
    """
    items = [AdminLocaleItem.model_validate(locale.model_dump()) for locale in result.items]
    return AdminLocaleList(items=items)
