(function exposeMapGeometry(root, factory) {
  const geometry = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = geometry;
  } else {
    root.MapGeometry = geometry;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function createMapGeometry() {
  const DEGREES_TO_RADIANS = Math.PI / 180;
  const RADIANS_TO_DEGREES = 180 / Math.PI;

  function normalizeLongitude(longitude) {
    return ((((longitude + 180) % 360) + 360) % 360) - 180;
  }

  function interpolateGreatCircle(origin, destination, samples = 64) {
    const lat1 = origin.lat * DEGREES_TO_RADIANS;
    const lon1 = origin.lng * DEGREES_TO_RADIANS;
    const lat2 = destination.lat * DEGREES_TO_RADIANS;
    const lon2 = destination.lng * DEGREES_TO_RADIANS;
    const first = [
      Math.cos(lat1) * Math.cos(lon1),
      Math.cos(lat1) * Math.sin(lon1),
      Math.sin(lat1),
    ];
    const second = [
      Math.cos(lat2) * Math.cos(lon2),
      Math.cos(lat2) * Math.sin(lon2),
      Math.sin(lat2),
    ];
    const dot = Math.max(-1, Math.min(1, first.reduce((sum, value, i) => sum + value * second[i], 0)));
    const angle = Math.acos(dot);
    const pointCount = Math.max(2, Math.ceil((angle / Math.PI) * samples) + 1);

    if (angle < 1e-8 || Math.abs(Math.sin(angle)) < 1e-8) {
      const longitudeDelta = normalizeLongitude(destination.lng - origin.lng);
      return Array.from({ length: pointCount }, (_, index) => {
        const fraction = index / (pointCount - 1);
        return {
          lat: origin.lat + (destination.lat - origin.lat) * fraction,
          lng: normalizeLongitude(origin.lng + longitudeDelta * fraction),
        };
      });
    }

    const sinAngle = Math.sin(angle);
    return Array.from({ length: pointCount }, (_, index) => {
      const fraction = index / (pointCount - 1);
      const firstWeight = Math.sin((1 - fraction) * angle) / sinAngle;
      const secondWeight = Math.sin(fraction * angle) / sinAngle;
      const x = firstWeight * first[0] + secondWeight * second[0];
      const y = firstWeight * first[1] + secondWeight * second[1];
      const z = firstWeight * first[2] + secondWeight * second[2];
      return {
        lat: Math.atan2(z, Math.hypot(x, y)) * RADIANS_TO_DEGREES,
        lng: normalizeLongitude(Math.atan2(y, x) * RADIANS_TO_DEGREES),
      };
    });
  }

  function splitAtAntimeridian(points) {
    if (points.length < 2) {
      return points.length ? [points] : [];
    }

    const segments = [[points[0]]];
    for (let index = 1; index < points.length; index += 1) {
      const previous = points[index - 1];
      const current = points[index];
      const delta = current.lng - previous.lng;

      if (Math.abs(delta) <= 180) {
        segments.at(-1).push(current);
        continue;
      }

      const crossesEast = delta < -180;
      const currentUnwrapped = current.lng + (crossesEast ? 360 : -360);
      const boundary = crossesEast ? 180 : -180;
      const fraction = (boundary - previous.lng) / (currentUnwrapped - previous.lng);
      const latitude = previous.lat + (current.lat - previous.lat) * fraction;
      segments.at(-1).push({ lat: latitude, lng: boundary });
      segments.push([
        { lat: latitude, lng: -boundary },
        current,
      ]);
    }

    return segments;
  }

  function greatCircleSegments(origin, destination, samples = 64) {
    return splitAtAntimeridian(interpolateGreatCircle(origin, destination, samples));
  }

  return Object.freeze({
    greatCircleSegments,
    interpolateGreatCircle,
    normalizeLongitude,
    splitAtAntimeridian,
  });
});
