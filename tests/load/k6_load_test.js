/**
 * K6 Load Testing Script
 * 
 * Alternative to Locust using K6 for load testing.
 * 
 * Usage:
 *   k6 run --vus 1000 --duration 10m k6_load_test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const shiftPostTime = new Trend('shift_post_duration');
const waveDispatchTime = new Trend('wave_dispatch_duration');

// Load test configuration
export const options = {
  stages: [
    { duration: '2m', target: 100 },   // Ramp up to 100 users
    { duration: '5m', target: 500 },   // Ramp up to 500 users
    { duration: '10m', target: 1000 }, // Peak load: 1000 users
    { duration: '5m', target: 500 },   // Ramp down
    { duration: '2m', target: 0 },     // Cool down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'], // 95% < 500ms, 99% < 1s
    errors: ['rate<0.01'],                          // Error rate < 1%
    http_req_failed: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  const actions = [
    viewAvailableShifts,
    updateProviderLocation,
    postNewShift,
    acceptShift,
    checkBillingSummary,
  ];
  
  // Random action
  const action = actions[Math.floor(Math.random() * actions.length)];
  action();
  
  sleep(Math.random() * 5 + 5); // 5-10 seconds
}

function viewAvailableShifts() {
  const response = http.get(`${BASE_URL}/api/v1/shifts/available`);
  
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 200ms': (r) => r.timings.duration < 200,
  }) || errorRate.add(1);
}

function updateProviderLocation() {
  const payload = JSON.stringify({
    provider_id: `provider-${Math.floor(Math.random() * 10000)}`,
    latitude: 39.2904 + (Math.random() - 0.5) * 0.2,
    longitude: -76.6122 + (Math.random() - 0.5) * 0.2,
  });
  
  const response = http.post(
    `${BASE_URL}/api/v1/location/update`,
    payload,
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  check(response, {
    'status is 200': (r) => r.status === 200,
  }) || errorRate.add(1);
}

function postNewShift() {
  const now = new Date();
  const shiftStart = new Date(now.getTime() + Math.random() * 48 * 3600000);
  const shiftEnd = new Date(shiftStart.getTime() + 8 * 3600000);
  
  const payload = JSON.stringify({
    facility_id: `facility-${Math.floor(Math.random() * 100)}`,
    shift_start: shiftStart.toISOString(),
    shift_end: shiftEnd.toISOString(),
    license_required: ['CNA', 'GNA', 'LPN'][Math.floor(Math.random() * 3)],
    hourly_rate: 25 + Math.random() * 10,
  });
  
  const response = http.post(
    `${BASE_URL}/api/v1/shifts`,
    payload,
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  shiftPostTime.add(response.timings.duration);
  
  check(response, {
    'status is 201': (r) => r.status === 201,
    'shift post < 300ms': (r) => r.timings.duration < 300,
  }) || errorRate.add(1);
}

function acceptShift() {
  const shiftId = `shift-${Math.floor(Math.random() * 10000)}`;
  const providerId = `provider-${Math.floor(Math.random() * 10000)}`;
  
  const response = http.post(
    `${BASE_URL}/api/v1/shifts/${shiftId}/accept`,
    JSON.stringify({ provider_id: providerId }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  waveDispatchTime.add(response.timings.duration);
  
  check(response, {
    'status is 200 or 404': (r) => r.status === 200 || r.status === 404,
  }) || errorRate.add(1);
}

function checkBillingSummary() {
  const facilityId = `facility-${Math.floor(Math.random() * 100)}`;
  
  const response = http.get(`${BASE_URL}/api/v1/billing/summary/${facilityId}`);
  
  check(response, {
    'status is 200': (r) => r.status === 200,
    'billing query < 500ms': (r) => r.timings.duration < 500,
  }) || errorRate.add(1);
}

export function handleSummary(data) {
  return {
    'load_test_results.json': JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data, options) {
  const indent = options?.indent || '';
  
  return `
${indent}Load Test Results:
${indent}  Checks Passed: ${data.metrics.checks.values.passes}
${indent}  Checks Failed: ${data.metrics.checks.values.fails}
${indent}  Average Response Time: ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms
${indent}  95th Percentile: ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms
${indent}  99th Percentile: ${data.metrics.http_req_duration.values['p(99)'].toFixed(2)}ms
${indent}  Error Rate: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%
${indent}  Requests Per Second: ${(data.metrics.http_reqs.values.rate).toFixed(2)}
  `;
}
