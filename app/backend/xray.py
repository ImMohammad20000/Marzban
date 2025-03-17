from __future__ import annotations

import json
from copy import deepcopy
from pathlib import PosixPath
from typing import Union

import commentjson

from app.models.proxy import ProxyTypes
from app.utils.crypto import get_cert_SANs, get_x25519_public_key
from config import XRAY_EXCLUDE_INBOUND_TAGS, XRAY_FALLBACKS_INBOUND_TAG


class XRayConfig(dict):
    def __init__(self, config: Union[dict, str, PosixPath] = {}):
        if isinstance(config, str):
            try:
                # considering string as json
                config = commentjson.loads(config)
            except (json.JSONDecodeError, ValueError):
                # considering string as file path
                with open(config, "r") as file:
                    config = commentjson.loads(file.read())

        if isinstance(config, PosixPath):
            with open(config, "r") as file:
                config = commentjson.loads(file.read())

        if isinstance(config, dict):
            config = deepcopy(config)

        super().__init__(config)
        self._validate()

        self.inbounds = []
        self.inbounds_by_protocol = {}
        self.inbounds_by_tag = {}
        self._fallbacks_inbound = self.get_inbound(XRAY_FALLBACKS_INBOUND_TAG)
        self._resolve_inbounds()

    def _validate(self):
        if not self.get("inbounds"):
            raise ValueError("config doesn't have inbounds")

        if not self.get("outbounds"):
            raise ValueError("config doesn't have outbounds")

        for inbound in self["inbounds"]:
            if not inbound.get("tag"):
                raise ValueError("all inbounds must have a unique tag")
            if "," in inbound.get("tag"):
                raise ValueError("character «,» is not allowed in inbound tag")
        for outbound in self["outbounds"]:
            if not outbound.get("tag"):
                raise ValueError("all outbounds must have a unique tag")

    def _resolve_inbounds(self):
        for inbound in self["inbounds"]:
            if inbound["protocol"] not in ProxyTypes._value2member_map_:
                continue

            if inbound["tag"] in XRAY_EXCLUDE_INBOUND_TAGS:
                continue

            if not inbound.get("settings"):
                inbound["settings"] = {}
            if not inbound["settings"].get("clients"):
                inbound["settings"]["clients"] = []

            settings = {
                "tag": inbound["tag"],
                "protocol": inbound["protocol"],
                "port": None,
                "network": "tcp",
                "tls": "none",
                "sni": [],
                "host": [],
                "path": "",
                "header_type": "",
                "is_fallback": False,
            }

            # port settings
            try:
                settings["port"] = inbound["port"]
            except KeyError:
                if self._fallbacks_inbound:
                    try:
                        settings["port"] = self._fallbacks_inbound["port"]
                        settings["is_fallback"] = True
                    except KeyError:
                        raise ValueError("fallbacks inbound doesn't have port")

            # stream settings
            if stream := inbound.get("streamSettings"):
                net = stream.get("network", "tcp")
                net_settings = stream.get(f"{net}Settings", {})
                security = stream.get("security")
                tls_settings = stream.get(f"{security}Settings")

                if settings["is_fallback"] is True:
                    # probably this is a fallback
                    security = self._fallbacks_inbound.get("streamSettings", {}).get("security")
                    tls_settings = self._fallbacks_inbound.get("streamSettings", {}).get(f"{security}Settings", {})

                settings["network"] = net

                if security == "tls":
                    # settings['fp']
                    # settings['alpn']
                    settings["tls"] = "tls"
                    for certificate in tls_settings.get("certificates", []):
                        if certificate.get("certificateFile", None):
                            with open(certificate["certificateFile"], "rb") as file:
                                cert = file.read()
                                settings["sni"].extend(get_cert_SANs(cert))

                        if certificate.get("certificate", None):
                            cert = certificate["certificate"]
                            if isinstance(cert, list):
                                cert = "\n".join(cert)
                            if isinstance(cert, str):
                                cert = cert.encode()
                            settings["sni"].extend(get_cert_SANs(cert))

                elif security == "reality":
                    settings["fp"] = "chrome"
                    settings["tls"] = "reality"
                    settings["sni"] = tls_settings.get("serverNames", [])

                    pvk = tls_settings.get("privateKey")
                    if not pvk:
                        raise ValueError(f"You need to provide privateKey in realitySettings of {inbound['tag']}")

                    settings["pbk"] = get_x25519_public_key(pvk)
                    if not settings.get("pbk"):
                        raise ValueError(f"You need to provide publicKey in realitySettings of {inbound['tag']}")
                    try:
                        settings["sids"] = tls_settings.get("shortIds")
                        settings["sids"][0]  # check if there is any shortIds
                    except (IndexError, TypeError):
                        raise ValueError(
                            f"You need to define at least one shortID in realitySettings of {inbound['tag']}"
                        )
                    try:
                        settings["spx"] = tls_settings.get("SpiderX")
                    except Exception:
                        settings["spx"] = ""

                if net in ("tcp", "raw"):
                    header = net_settings.get("header", {})
                    request = header.get("request", {})
                    path = request.get("path")
                    host = request.get("headers", {}).get("Host")

                    settings["header_type"] = header.get("type", "")

                    if isinstance(path, str) or isinstance(host, str):
                        raise ValueError(
                            f"Settings of {inbound['tag']} for path and host must be list, not str\n"
                            "https://xtls.github.io/config/transports/tcp.html#httpheaderobject"
                        )

                    if path and isinstance(path, list):
                        settings["path"] = path[0]

                    if host and isinstance(host, list):
                        settings["host"] = host

                elif net == "ws":
                    path = net_settings.get("path", "")
                    host = net_settings.get("host", "") or net_settings.get("headers", {}).get("Host")

                    settings["header_type"] = ""

                    if isinstance(path, list) or isinstance(host, list):
                        raise ValueError(
                            f"Settings of {inbound['tag']} for path and host must be str, not list\n"
                            "https://xtls.github.io/config/transports/websocket.html#websocketobject"
                        )

                    if isinstance(path, str):
                        settings["path"] = path

                    if isinstance(host, str):
                        settings["host"] = [host]

                elif net == "grpc" or net == "gun":
                    settings["header_type"] = ""
                    settings["path"] = net_settings.get("serviceName", "")
                    host = net_settings.get("authority", "")
                    settings["host"] = [host]

                elif net == "quic":
                    settings["header_type"] = net_settings.get("header", {}).get("type", "")
                    settings["path"] = net_settings.get("key", "")
                    settings["host"] = [net_settings.get("security", "")]

                elif net == "httpupgrade":
                    settings["path"] = net_settings.get("path", "")
                    host = net_settings.get("host", "")
                    settings["host"] = [host]

                elif net in ("splithttp", "xhttp"):
                    settings["path"] = net_settings.get("path", "")
                    host = net_settings.get("host", "")
                    settings["host"] = [host]
                    settings["downloadSettings"] = net_settings.get("downloadSettings", {})
                    settings["mode"] = net_settings.get("mode", "auto")

                elif net == "kcp":
                    header = net_settings.get("header", {})

                    settings["header_type"] = header.get("type", "")
                    settings["host"] = header.get("domain", "")
                    settings["path"] = net_settings.get("seed", "")

                elif net in ("http", "h2", "h3"):
                    net_settings = stream.get("httpSettings", {})

                    settings["host"] = net_settings.get("host") or net_settings.get("Host", "")
                    settings["path"] = net_settings.get("path", "")

                else:
                    settings["path"] = net_settings.get("path", "")
                    host = net_settings.get("host", {}) or net_settings.get("Host", {})
                    if host and isinstance(host, str):
                        settings["host"] = host
                    elif host and isinstance(host, list):
                        settings["host"] = host[0]

            self.inbounds.append(inbound["tag"])
            self.inbounds_by_tag[inbound["tag"]] = settings

            try:
                self.inbounds_by_protocol[inbound["protocol"]].append(settings)
            except KeyError:
                self.inbounds_by_protocol[inbound["protocol"]] = [settings]

    def get_inbound(self, tag) -> dict:
        for inbound in self["inbounds"]:
            if inbound["tag"] == tag:
                return inbound

    def get_outbound(self, tag) -> dict:
        for outbound in self["outbounds"]:
            if outbound["tag"] == tag:
                return outbound

    def to_json(self, **json_kwargs):
        return json.dumps(self, **json_kwargs)

    def copy(self):
        return deepcopy(self)
