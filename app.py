from xml.dom import minidom

from flask import Flask, render_template, request, jsonify
import json
import requests  # Import the requests module
from xml.etree import ElementTree as ET

app = Flask(__name__)


def load_config():
    # Load services from config.json
    with open('config.json', 'r') as file:
        config_data = json.load(file)
    # print(config_data)
    return config_data["webServices"]


def execute_service_logic(service, operation_name, iteration):

    operation = next(
        (op for op in service['operations'] if op['operationName'] == operation_name),
        None
    )

    # Extract the useCase value as the description
    usecase = operation.get("useCase", "No description available")

    try:
        if not operation:
            return {
                "status": "FAIL",
                "responseText": f"Operation with name '{operation_name}' not found in service configuration.",
                "description": usecase
            }

        endpoint = operation.get("endpoint", "")
        if not endpoint:
            return {
                "status": "FAIL",
                "responseText": f"Endpoint not specified in the operation configuration for '{operation_name}'.",
                "description": usecase
            }

        headers = operation.get("additionalHeaders", {})
        sample_request_location = operation.get("sampleRequestLocation", "")

        if sample_request_location:
            with open(sample_request_location, 'r') as file:
                file_content = file.read()

                # Check if the content is JSON
                try:
                    payload = json.loads(file_content)
                except json.JSONDecodeError:
                    # If not JSON, assume it's XML
                    try:
                        payload = ET.fromstring(file_content)
                    except ET.ParseError:
                        payload = None
        else:
            payload = None

        # print("operation_name" + operation_name)
        if not sample_request_location:
            # If operation_name is not specified or sample_request_location is blank, default to GET
            response = requests.get(endpoint, headers=headers)
        else:
            if isinstance(payload, ET.Element):
                # If payload is XML, send as text
                payload_xml = ET.tostring(payload, encoding='utf-8').decode('utf-8')
                headers['Content-Type'] = 'application/xml'
                response = requests.post(endpoint, data=payload_xml, headers=headers)
            else:
                # If payload is JSON, send as JSON
                response = requests.post(endpoint, json=payload, headers=headers)

        # Print request details
        print("Request URL:", response.text)
        print("Request Method:", response.request.method)
        print("Request Headers:", response.request.headers)
        print("Request Body:")
        if payload:
            if isinstance(payload, dict):
                payload_json = json.dumps(payload, indent=2)
                print(payload_json)
            else:
                print(payload)

        # print(response.text)
        success_criteria = operation.get("successCriteria", None)

        if success_criteria:
            # Check if successCriteria is present in the config
            result_status = "PASS" if success_criteria in response.text else "FAIL"
        else:
            # If successCriteria is not present, check for status code 200 or 201
            result_status = "PASS" if response.status_code in [200, 201] else "FAIL"

        response_text = response.text

    except requests.ConnectionError as ce:
        # Handle ConnectionError exception
        # print(f"ConnectionError: {ce}")
        result_status = "FAIL"
        response_text = str(ce)

    result = {
        "status": result_status,
        "responseText": response_text,
        "description": usecase
    }

    return result


def execute_service(service_name, iteration_counter):
    # Split the service name into serviceName and operationName
    serviceName, operationName = service_name.split(':')

    service = next(
        (
            s
            for s in load_config()
            if s["serviceName"] == serviceName
               and any(op["operationName"] == operationName for op in s["operations"])
        ),
        None
    )

    if service:
        service_results = []
        passed_iterations = 0  # Counter for passed iterations

        for iteration in range(1, iteration_counter + 1):
            iteration_result = execute_service_logic(service, operationName, iteration)
            service_results.append(iteration_result)

            if iteration_result["status"] == "PASS":
                passed_iterations += 1

        overall_status = f"{passed_iterations}/{iteration_counter} - "
        overall_status += "GREEN" if all(result["status"] == "PASS" for result in service_results) else "RED"

        return {
            "serviceName": service_name,
            "overallStatus": overall_status,
            "iterations": service_results
        }
    else:
        return None


@app.route('/')
def index():
    services = load_config()
    return render_template('index.html', services=services)


@app.route('/execute', methods=['POST'])
def execute():
    selected_services = request.json.get('selectedServices', [])
    iteration_counter = int(request.json.get('iterationCounter', 1))
    results = []
    # print(selected_services)
    # print(results)
    for service_name in selected_services:
        service_result = execute_service(service_name, iteration_counter)
        if service_result:
            results.append(service_result)

    return jsonify(results)


if __name__ == '__main__':
    app.run(debug=True)
