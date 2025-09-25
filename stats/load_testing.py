"""
Load testing utilities for Story 18 API Performance Optimization.

Provides tools for performance testing, load simulation, and benchmarking
API endpoints to validate sub-500ms response time requirements.
"""
import time
import asyncio
import statistics
import concurrent.futures
from django.test import Client, TransactionTestCase
from django.urls import reverse
from django.db import connection
from django.conf import settings
import json
import logging

logger = logging.getLogger('stats.load_testing')


class PerformanceBenchmark:
    """Performance benchmarking utility for API endpoints."""

    def __init__(self):
        self.client = Client()
        self.results = {}

    def benchmark_endpoint(self, url, method='GET', data=None, iterations=100, concurrent=False):
        """Benchmark a single endpoint with specified iterations."""
        logger.info(f"Benchmarking {method} {url} with {iterations} iterations")

        response_times = []
        query_counts = []
        errors = 0

        if concurrent:
            return self._benchmark_concurrent(url, method, data, iterations)
        else:
            return self._benchmark_sequential(url, method, data, iterations)

    def _benchmark_sequential(self, url, method='GET', data=None, iterations=100):
        """Sequential benchmark execution."""
        response_times = []
        query_counts = []
        status_codes = []
        errors = 0

        for i in range(iterations):
            initial_query_count = len(connection.queries)
            start_time = time.time()

            try:
                if method.upper() == 'GET':
                    response = self.client.get(url, data or {})
                elif method.upper() == 'POST':
                    response = self.client.post(
                        url,
                        json.dumps(data or {}),
                        content_type='application/json'
                    )

                end_time = time.time()
                response_time = (end_time - start_time) * 1000

                response_times.append(response_time)
                query_counts.append(len(connection.queries) - initial_query_count)
                status_codes.append(response.status_code)

                if response.status_code >= 400:
                    errors += 1
                    logger.warning(f"Error response: {response.status_code} on iteration {i+1}")

            except Exception as e:
                errors += 1
                logger.error(f"Exception on iteration {i+1}: {e}")
                continue

        return self._calculate_metrics(url, response_times, query_counts, status_codes, errors)

    def _benchmark_concurrent(self, url, method='GET', data=None, iterations=100, max_workers=10):
        """Concurrent benchmark execution using ThreadPoolExecutor."""
        response_times = []
        query_counts = []
        status_codes = []
        errors = 0

        def single_request():
            client = Client()
            initial_query_count = len(connection.queries)
            start_time = time.time()

            try:
                if method.upper() == 'GET':
                    response = client.get(url, data or {})
                elif method.upper() == 'POST':
                    response = client.post(
                        url,
                        json.dumps(data or {}),
                        content_type='application/json'
                    )

                end_time = time.time()
                response_time = (end_time - start_time) * 1000

                return {
                    'response_time': response_time,
                    'query_count': len(connection.queries) - initial_query_count,
                    'status_code': response.status_code,
                    'error': response.status_code >= 400
                }
            except Exception as e:
                logger.error(f"Concurrent request failed: {e}")
                return {
                    'response_time': 0,
                    'query_count': 0,
                    'status_code': 500,
                    'error': True
                }

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(single_request) for _ in range(iterations)]

            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                response_times.append(result['response_time'])
                query_counts.append(result['query_count'])
                status_codes.append(result['status_code'])
                if result['error']:
                    errors += 1

        return self._calculate_metrics(url, response_times, query_counts, status_codes, errors)

    def _calculate_metrics(self, url, response_times, query_counts, status_codes, errors):
        """Calculate performance metrics from benchmark data."""
        if not response_times:
            return {
                'url': url,
                'error': 'No successful requests',
                'total_requests': 0,
                'errors': errors
            }

        # Filter out zero response times (errors)
        valid_times = [t for t in response_times if t > 0]
        valid_queries = [q for q, t in zip(query_counts, response_times) if t > 0]

        metrics = {
            'url': url,
            'total_requests': len(response_times),
            'successful_requests': len(valid_times),
            'errors': errors,
            'error_rate': (errors / len(response_times)) * 100 if response_times else 100,

            # Response time metrics
            'response_time': {
                'min': min(valid_times) if valid_times else 0,
                'max': max(valid_times) if valid_times else 0,
                'mean': statistics.mean(valid_times) if valid_times else 0,
                'median': statistics.median(valid_times) if valid_times else 0,
                'p95': self._percentile(valid_times, 95) if valid_times else 0,
                'p99': self._percentile(valid_times, 99) if valid_times else 0,
            },

            # Database query metrics
            'database_queries': {
                'min': min(valid_queries) if valid_queries else 0,
                'max': max(valid_queries) if valid_queries else 0,
                'mean': statistics.mean(valid_queries) if valid_queries else 0,
            },

            # Performance assessment
            'performance_grade': self._grade_performance(valid_times),
            'meets_sla': all(t < 500 for t in valid_times) if valid_times else False,  # 500ms SLA
        }

        return metrics

    def _percentile(self, data, percentile):
        """Calculate percentile value."""
        if not data:
            return 0
        size = len(data)
        return sorted(data)[int(size * percentile / 100)]

    def _grade_performance(self, response_times):
        """Grade endpoint performance based on response times."""
        if not response_times:
            return 'F'

        p95_time = self._percentile(response_times, 95)

        if p95_time < 100:
            return 'A+'
        elif p95_time < 200:
            return 'A'
        elif p95_time < 300:
            return 'B'
        elif p95_time < 500:
            return 'C'
        elif p95_time < 1000:
            return 'D'
        else:
            return 'F'

    def benchmark_all_endpoints(self, iterations=50):
        """Benchmark all major API endpoints."""
        endpoints = [
            '/api/stats/',
            '/api/stats/recent-tracks/',
            '/api/stats/top-artists/?period=30d',
            '/api/stats/top-albums/?period=30d',
            '/api/stats/top-tracks/?period=30d',
            '/api/stats/scrobbles/chart/?period=30d&granularity=daily',
            '/api/stats/summary/',
        ]

        results = {}
        total_start_time = time.time()

        for endpoint in endpoints:
            logger.info(f"Benchmarking endpoint: {endpoint}")
            results[endpoint] = self.benchmark_endpoint(endpoint, iterations=iterations)

        total_time = time.time() - total_start_time

        # Generate summary report
        summary = self._generate_summary_report(results, total_time, iterations)

        return {
            'endpoints': results,
            'summary': summary
        }

    def _generate_summary_report(self, results, total_time, iterations):
        """Generate summary performance report."""
        total_requests = sum(r['total_requests'] for r in results.values())
        total_errors = sum(r['errors'] for r in results.values())

        all_response_times = []
        all_grades = []
        sla_compliance = []

        for result in results.values():
            if 'response_time' in result and result['response_time']['mean'] > 0:
                all_response_times.append(result['response_time']['mean'])
                all_grades.append(result['performance_grade'])
                sla_compliance.append(result['meets_sla'])

        return {
            'total_time': total_time,
            'total_requests': total_requests,
            'total_errors': total_errors,
            'error_rate': (total_errors / total_requests) * 100 if total_requests else 0,
            'average_response_time': statistics.mean(all_response_times) if all_response_times else 0,
            'overall_grade': max(set(all_grades), key=all_grades.count) if all_grades else 'F',
            'sla_compliance_rate': (sum(sla_compliance) / len(sla_compliance)) * 100 if sla_compliance else 0,
            'requests_per_second': total_requests / total_time if total_time > 0 else 0,
        }


class LoadTestCase(TransactionTestCase):
    """Django test case for load testing API endpoints."""

    def setUp(self):
        self.benchmark = PerformanceBenchmark()

    def test_api_performance_sla(self):
        """Test that API endpoints meet the 500ms SLA requirement."""
        # Light load test with key endpoints
        endpoints = [
            '/api/stats/recent-tracks/?limit=10',
            '/api/stats/top-artists/?period=30d&limit=10',
            '/api/stats/summary/',
        ]

        failed_endpoints = []

        for endpoint in endpoints:
            result = self.benchmark.benchmark_endpoint(endpoint, iterations=20)

            if not result.get('meets_sla', False):
                failed_endpoints.append({
                    'endpoint': endpoint,
                    'p95_time': result['response_time']['p95']
                })

        if failed_endpoints:
            fail_msg = "Endpoints failed to meet 500ms SLA:\n"
            for item in failed_endpoints:
                fail_msg += f"- {item['endpoint']}: {item['p95_time']:.1f}ms (P95)\n"
            self.fail(fail_msg)

    def test_concurrent_load_handling(self):
        """Test API performance under concurrent load."""
        result = self.benchmark.benchmark_endpoint(
            '/api/stats/recent-tracks/?limit=20',
            iterations=50,
            concurrent=True
        )

        # Assert performance criteria
        self.assertLess(result['response_time']['p95'], 1000,
                       "P95 response time should be under 1000ms under concurrent load")
        self.assertLess(result['error_rate'], 5,
                       "Error rate should be less than 5%")
        self.assertGreater(result['successful_requests'], 45,
                          "At least 90% of requests should succeed")


def run_performance_baseline():
    """Run baseline performance tests and save results."""
    benchmark = PerformanceBenchmark()

    logger.info("Starting comprehensive performance baseline test")
    results = benchmark.benchmark_all_endpoints(iterations=100)

    # Save results to file
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"performance_baseline_{timestamp}.json"

    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"Performance baseline saved to {filename}")

    # Print summary
    summary = results['summary']
    print("\n" + "="*60)
    print("PERFORMANCE BASELINE SUMMARY")
    print("="*60)
    print(f"Total Requests: {summary['total_requests']}")
    print(f"Total Errors: {summary['total_errors']} ({summary['error_rate']:.1f}%)")
    print(f"Average Response Time: {summary['average_response_time']:.1f}ms")
    print(f"Overall Grade: {summary['overall_grade']}")
    print(f"SLA Compliance Rate: {summary['sla_compliance_rate']:.1f}%")
    print(f"Requests per Second: {summary['requests_per_second']:.1f}")

    # Print endpoint details
    print("\nENDPOINT PERFORMANCE:")
    for endpoint, result in results['endpoints'].items():
        if 'response_time' in result:
            print(f"{endpoint:<50} {result['response_time']['mean']:>6.1f}ms (avg) "
                  f"{result['response_time']['p95']:>6.1f}ms (P95) "
                  f"Grade: {result['performance_grade']}")

    return results


if __name__ == '__main__':
    run_performance_baseline()