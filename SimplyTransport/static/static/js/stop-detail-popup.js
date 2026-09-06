/**
 * Shared helpers for map popups: GET /api/v1/stop/{id}/detailed (StopDetailed).
 * Loaded before stop-map.js, nearby-map.js, route-map.js, static-stop-map.js.
 */
(function (global) {
	"use strict";

	function escapeHtml(s) {
		if (s === null || s === undefined) {
			return "";
		}
		return String(s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	/** @param {boolean | null | undefined} value */
	function featureBoolToEmoji(value) {
		if (value === true) {
			return "✅";
		}
		if (value === false) {
			return "❌";
		}
		return "—";
	}

	function fetchStopDetailed(stopId) {
		return fetch(`/api/v1/stop/${encodeURIComponent(stopId)}/detailed`).then(
			(r) => {
				if (!r.ok) {
					throw new Error("Stop details not available");
				}
				return r.json();
			},
		);
	}

	/**
	 * @param {object} detail - StopDetailed JSON
	 * @param {string} directionForRouteLinks - direction segment for /realtime/route/... links
	 */
	function buildPopupHtmlFromDetailed(detail, directionForRouteLinks) {
		const stop = detail.stop;
		const code = stop.code || "";
		const title = `${code} - ${stop.name}`.trim();
		const routes = detail.routes || [];
		const dir = directionForRouteLinks || "OUTBOUND";
		const routesHtml = routes
			.map(
				(r) =>
					`<a href="/realtime/route/${escapeHtml(r.route_id)}/${dir}">${escapeHtml(r.short_name)}</a> — ${escapeHtml(r.long_name)}`,
			)
			.join("<br>");

		let featuresHtml = "";
		if (detail.stop_features) {
			const sf = detail.stop_features;
			featuresHtml =
				`<p class="map-popup-block map-popup-muted">Wheelchair accessible: ${featureBoolToEmoji(sf.wheelchair_accessible)}<br>` +
				`Bus shelter: ${featureBoolToEmoji(sf.shelter_active)}<br>` +
				`Realtime display: ${featureBoolToEmoji(sf.rtpi_active)}</p>`;
		}

		let streetBlock = "";
		const streetUrl = detail.street_view_url || "";
		if (streetUrl) {
			streetBlock =
				`<p class="map-popup-block"><a class="map-popup-link" href="${escapeHtml(streetUrl)}" target="_blank" rel="noopener noreferrer">Street view</a></p>`;
		}

		return (
			`<div class="map-popup-inner">` +
			`<h4 class="map-popup-title"><a href="/realtime/stop/${escapeHtml(stop.id)}">${escapeHtml(title)}</a></h4>` +
			streetBlock +
			featuresHtml +
			`<p class="map-popup-block map-popup-routes-head"><strong>${routes.length} Routes</strong></p>` +
			`<p class="map-popup-routes">${routesHtml}</p>` +
			`</div>`
		);
	}

	/** @param {object} stop - StopMapStop from map payload */
	function buildLoadingPopupHtml(stop) {
		const code = stop.code || "";
		const title = `${code} - ${stop.name}`.trim();
		return (
			`<div class="map-popup-inner">` +
			`<h4 class="map-popup-title"><a href="/realtime/stop/${escapeHtml(stop.stop_id)}">${escapeHtml(title)}</a></h4>` +
			`<p class="map-popup-muted">Loading routes…</p>` +
			`</div>`
		);
	}

	/** @param {object} stop - StopMapStop from map payload */
	function buildErrorPopupHtml(stop) {
		const code = stop.code || "";
		const title = `${code} - ${stop.name}`.trim();
		return (
			`<div class="map-popup-inner">` +
			`<h4 class="map-popup-title"><a href="/realtime/stop/${escapeHtml(stop.stop_id)}">${escapeHtml(title)}</a></h4>` +
			`<p class="map-popup-muted">Could not load stop details.</p>` +
			`</div>`
		);
	}

	/** @param {object} stop - StopMapStop from map payload */
	function buildStopTooltipHtml(stop) {
		const code = stop.code || "";
		const title = `${code} - ${stop.name}`.trim();
		return `<div class="map-stop-tooltip-inner">${escapeHtml(title)}</div>`;
	}

	/**
	 * Relative label from ISO 8601 (mirrors server mins_ago_updated style).
	 * @param {string} iso
	 */
	function formatRelativeFromIso(iso) {
		if (!iso) {
			return "";
		}
		const t = new Date(iso).getTime();
		if (Number.isNaN(t)) {
			return "";
		}
		const mins = Math.floor((Date.now() - t) / 60000);
		if (mins < 1) {
			return "Less than a minute ago";
		}
		if (mins === 1) {
			return "1 min ago";
		}
		return `${mins} mins ago`;
	}

	/**
	 * @param {object} props - GeoJSON feature properties from map payload vehicles (includes map_direction)
	 */
	function buildVehiclePopupHtml(props) {
		const routeLabel = props.route_short_name || props.route_id || "";
		const agency = props.agency_name || "";
		const dir =
			props.map_direction !== undefined && props.map_direction !== null
				? String(props.map_direction)
				: "OUTBOUND";
		const routeHref = `/realtime/route/${encodeURIComponent(String(props.route_id))}/${encodeURIComponent(dir)}`;
		const titleText = [routeLabel, agency].filter(Boolean).join(" - ") || "Vehicle";
		const titleInner =
			props.route_id != null && props.route_id !== ""
				? `<a class="map-popup-link map-popup-vehicle-head-link" href="${routeHref}">${escapeHtml(titleText)}</a>`
				: escapeHtml(titleText);
		const iso = props.time_of_update || "";
		let lastUpdatedLine = "";
		if (iso) {
			const d = new Date(iso);
			const local = !Number.isNaN(d.getTime())
				? d.toLocaleString(undefined, {
						dateStyle: "medium",
						timeStyle: "medium",
					})
				: iso;
			const rel = formatRelativeFromIso(iso);
			lastUpdatedLine = `<p class="map-popup-block map-popup-muted">Last updated: ${escapeHtml(local)}<br>${escapeHtml(rel)}</p>`;
		}
		return (
			`<div class="map-popup-inner map-popup-inner--vehicle">` +
			`<h4 class="map-popup-vehicle-head">${titleInner}</h4>` +
			lastUpdatedLine +
			`</div>`
		);
	}

	global.StopMapPopup = {
		fetchStopDetailed,
		buildPopupHtmlFromDetailed,
		buildLoadingPopupHtml,
		buildErrorPopupHtml,
		buildStopTooltipHtml,
		buildVehiclePopupHtml,
		formatRelativeFromIso,
	};
})(window);
