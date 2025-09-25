"""
Management command for API performance benchmarking.

Story 18: API Performance Optimization
Command to run comprehensive performance tests and validate sub-500ms SLA.
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import json
import time
from stats.load_testing import PerformanceBenchmark, run_performance_baseline


class Command(BaseCommand):
    help = 'Run API performance benchmarks and validate response times'

    def add_arguments(self, parser):
        parser.add_argument(
            '--endpoint',
            type=str,
            help='Specific endpoint to benchmark (e.g., /api/stats/recent-tracks/)',
        )
        parser.add_argument(
            '--iterations',
            type=int,
            default=50,
            help='Number of test iterations (default: 50)',
        )
        parser.add_argument(
            '--concurrent',
            action='store_true',
            help='Run concurrent load testing',
        )
        parser.add_argument(
            '--save-results',
            type=str,
            help='Save results to JSON file',
        )
        parser.add_argument(
            '--sla-check',
            action='store_true',
            help='Only check SLA compliance (500ms threshold)',
        )
        parser.add_argument(
            '--baseline',
            action='store_true',
            help='Run comprehensive baseline test of all endpoints',
        )

    def handle(self, *args, **options):
        """Execute performance benchmark command."""

        # Ensure we're not in production
        if not settings.DEBUG:
            self.stdout.write(
                self.style.WARNING('Warning: Running performance tests in production environment')
            )

        benchmark = PerformanceBenchmark()

        if options['baseline']:
            self.stdout.write('Running comprehensive baseline performance test...')
            results = run_performance_baseline()
            self.display_summary(results['summary'])
            return

        if options['endpoint']:
            # Test specific endpoint
            self.stdout.write(f"Benchmarking endpoint: {options['endpoint']}")

            result = benchmark.benchmark_endpoint(
                options['endpoint'],
                iterations=options['iterations'],
                concurrent=options['concurrent']
            )

            self.display_endpoint_result(options['endpoint'], result)

            if options['sla_check']:
                self.check_sla_compliance([result])

        else:
            # Test all endpoints
            self.stdout.write('Running comprehensive API performance test...')

            results = benchmark.benchmark_all_endpoints(
                iterations=options['iterations']
            )

            self.display_summary(results['summary'])
            self.display_all_endpoints(results['endpoints'])

            if options['sla_check']:
                self.check_sla_compliance(results['endpoints'].values())

            if options['save_results']:
                self.save_results(results, options['save_results'])

    def display_endpoint_result(self, endpoint, result):
        """Display results for a single endpoint."""
        if 'error' in result:
            self.stdout.write(self.style.ERROR(f"Error: {result['error']}"))
            return

        rt = result['response_time']
        db = result['database_queries']

        self.stdout.write('\n' + '='*60)
        self.stdout.write(f"ENDPOINT: {endpoint}")
        self.stdout.write('='*60)

        # Request summary
        self.stdout.write(f"Total Requests: {result['total_requests']}")
        self.stdout.write(f"Successful: {result['successful_requests']}")
        self.stdout.write(f"Errors: {result['errors']} ({result['error_rate']:.1f}%)")

        # Response time metrics
        self.stdout.write(f"\nResponse Time (ms):")
        self.stdout.write(f"  Mean:   {rt['mean']:8.1f}")
        self.stdout.write(f"  Median: {rt['median']:8.1f}")
        self.stdout.write(f"  Min:    {rt['min']:8.1f}")
        self.stdout.write(f"  Max:    {rt['max']:8.1f}")
        self.stdout.write(f"  P95:    {rt['p95']:8.1f}")
        self.stdout.write(f"  P99:    {rt['p99']:8.1f}")

        # Database metrics
        self.stdout.write(f"\nDatabase Queries:")
        self.stdout.write(f"  Mean: {db['mean']:6.1f}")
        self.stdout.write(f"  Min:  {db['min']:6.0f}")
        self.stdout.write(f"  Max:  {db['max']:6.0f}")

        # Performance assessment
        grade_style = self.style.SUCCESS if result['performance_grade'] in ['A+', 'A', 'B'] else self.style.WARNING
        sla_style = self.style.SUCCESS if result['meets_sla'] else self.style.ERROR

        self.stdout.write(f"\nPerformance Grade: ", ending='')
        self.stdout.write(grade_style(result['performance_grade']))
        self.stdout.write(f"SLA Compliance (500ms): ", ending='')
        self.stdout.write(sla_style('PASS' if result['meets_sla'] else 'FAIL'))

    def display_summary(self, summary):
        """Display overall performance summary."""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('PERFORMANCE SUMMARY')
        self.stdout.write('='*60)

        self.stdout.write(f"Total Requests: {summary['total_requests']}")
        self.stdout.write(f"Total Errors: {summary['total_errors']} ({summary['error_rate']:.1f}%)")
        self.stdout.write(f"Average Response Time: {summary['average_response_time']:.1f}ms")
        self.stdout.write(f"Overall Grade: {summary['overall_grade']}")
        self.stdout.write(f"SLA Compliance Rate: {summary['sla_compliance_rate']:.1f}%")
        self.stdout.write(f"Requests per Second: {summary['requests_per_second']:.1f}")

    def display_all_endpoints(self, endpoints):
        """Display summary table of all endpoint results."""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('ENDPOINT PERFORMANCE DETAILS')
        self.stdout.write('='*80)

        header = f"{'Endpoint':<40} {'Avg (ms)':<10} {'P95 (ms)':<10} {'Grade':<6} {'SLA':<6}"
        self.stdout.write(header)
        self.stdout.write('-' * 80)

        for endpoint, result in endpoints.items():
            if 'response_time' in result:
                avg_time = result['response_time']['mean']
                p95_time = result['response_time']['p95']
                grade = result['performance_grade']
                sla = 'PASS' if result['meets_sla'] else 'FAIL'

                # Truncate long endpoint names
                display_endpoint = endpoint[:38] + '..' if len(endpoint) > 40 else endpoint

                line = f"{display_endpoint:<40} {avg_time:>7.1f} {p95_time:>9.1f} {grade:>6} {sla:>6}"

                # Color code based on performance
                if result['meets_sla']:
                    self.stdout.write(self.style.SUCCESS(line))
                elif avg_time < 1000:
                    self.stdout.write(self.style.WARNING(line))
                else:
                    self.stdout.write(self.style.ERROR(line))

    def check_sla_compliance(self, results):
        """Check and report SLA compliance."""
        failed_endpoints = []

        for result in results:
            if isinstance(result, dict) and not result.get('meets_sla', True):
                failed_endpoints.append({
                    'endpoint': result.get('url', 'Unknown'),
                    'p95_time': result.get('response_time', {}).get('p95', 0)
                })

        if failed_endpoints:
            self.stdout.write('\n' + self.style.ERROR('SLA COMPLIANCE FAILURES:'))
            for item in failed_endpoints:
                self.stdout.write(
                    self.style.ERROR(f"❌ {item['endpoint']}: {item['p95_time']:.1f}ms (P95)")
                )
            raise CommandError('One or more endpoints failed to meet 500ms SLA requirement')
        else:
            self.stdout.write('\n' + self.style.SUCCESS('✅ All endpoints meet 500ms SLA requirement'))

    def save_results(self, results, filename):
        """Save benchmark results to JSON file."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        if not filename.endswith('.json'):
            filename = f"{filename}_{timestamp}.json"

        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
            self.stdout.write(f"\n✅ Results saved to: {filename}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to save results: {e}"))