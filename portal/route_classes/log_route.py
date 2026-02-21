"""
LogRouting
"""
import json
import time
from typing import Callable, Dict, Any

from fastapi import Request, Response
from fastapi.routing import APIRoute

from portal.config import settings
from portal.libs.logger import logger


class LogRoute(APIRoute):
    """LogRouting"""

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        """
        Check if a key contains sensitive keywords.

        :param key: Key name to check
        :return: True if key is sensitive, False otherwise
        """
        key_lower = key.lower()
        return any(
            sensitive_keyword in key_lower
            for sensitive_keyword in settings.SENSITIVE_PARAMS
        )

    def filter_sensitive_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter sensitive parameters from query params to prevent logging sensitive information.

        :param params: Dictionary of query parameters
        :return: Dictionary with sensitive values replaced by "********"
        """
        filtered_params = {}
        for key, value in params.items():
            if self._is_sensitive_key(key):
                filtered_params[key] = "********"
            else:
                filtered_params[key] = value
        return filtered_params

    def filter_sensitive_data(self, data: Any) -> Any:
        """
        Recursively filter sensitive data from nested structures (dict, list).

        :param data: Data structure to filter (dict, list, or primitive)
        :return: Filtered data structure with sensitive values replaced by "********"
        """
        if isinstance(data, dict):
            filtered_dict = {}
            for key, value in data.items():
                if self._is_sensitive_key(key):
                    filtered_dict[key] = "********"
                else:
                    filtered_dict[key] = self.filter_sensitive_data(value)
            return filtered_dict
        elif isinstance(data, list):
            return [self.filter_sensitive_data(item) for item in data]
        else:
            return data

    def filter_request_body(self, body_str: str) -> str:
        """
        Filter sensitive information from request body string.

        :param body_str: Request body as string
        :return: Filtered request body as string
        """
        if not body_str or not body_str.strip():
            return body_str

        try:
            # Try to parse as JSON
            body_data = json.loads(body_str)
            filtered_data = self.filter_sensitive_data(body_data)
            return json.dumps(filtered_data, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError, TypeError):
            # If not JSON, return as is (could be form data, plain text, etc.)
            return body_str

    def get_route_handler(self) -> Callable:
        """
        :return:
        """
        origin_handler = super().get_route_handler()

        async def route_handler(request: Request) -> Response:
            """

            :param request:
            :return:
            """
            # Before controller, get request body
            start = time.time()
            request_body = await request.body()
            # Filter sensitive parameters from query params
            filtered_params = self.filter_sensitive_params(dict(request.query_params))
            request_message = {
                "http.request.method": request.method,
                "http.request.path": request.url.path,
                "http.request.params": filtered_params
            }
            if request.method in ("POST", "PUT", "PATCH"):
                try:
                    body_str = request_body.decode()
                    # Filter sensitive information from request body
                    filtered_body = self.filter_request_body(body_str)
                    request_message["http.request.body"] = filtered_body
                except Exception as exc:  # noqa
                    logger.warning(exc)
                    request_message["http.request.body"] = ""
            logger.info(request_message)

            # Execute the controller
            response: Response = await origin_handler(request)
            try:
                # After controller process, get response status, body
                try:
                    response_body = response.body.decode()
                except Exception as exc:  # noqa
                    logger.warning(exc)
                    response_body = ""

                response_message = {
                    "response.type": type(response).__name__,
                    "response.status_code": response.status_code,
                    "response.duration": round((time.time() - start) * 1000),
                    "response.body": response_body,
                }
                logger.info(response_message)
                return response
            except Exception as exc:
                logger.warning(exc)
                return response

        return route_handler
