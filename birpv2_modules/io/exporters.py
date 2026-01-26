#!/usr/bin/env python
"""
Export module for BIRP
Provides export functionality in multiple formats (JSON, CSV, HTML, XML)
"""

import json
import csv
from datetime import datetime


def export_to_json(history, filename, pretty=True):
	"""
	Export transaction history to JSON format

	Args:
		history: History object containing transactions
		filename (str): Output file path
		pretty (bool): Pretty print JSON (default: True)

	Returns:
		bool: Success status
	"""
	try:
		transactions = []
		for i, trans in enumerate(history):
			trans_dict = {
				'id': i,
				'timestamp': str(trans.timestamp),
				'host': trans.host,
				'key': trans.key,
				'comment': trans.comment,
				'request': {
					'screen': trans.request.stringbuffer,
					'rows': trans.request.rows,
					'cols': trans.request.cols,
					'protected_fields': [
						{
							'row': f.row,
							'col': f.col,
							'contents': f.contents,
							'hidden': f.hidden == 1,
							'protected': f.protected == 1
						}
						for f in trans.request.protected_fields
					],
					'input_fields': [
						{
							'row': f.row,
							'col': f.col,
							'contents': f.contents
						}
						for f in trans.request.input_fields
					],
					'hidden_fields': [
						{
							'row': f.row,
							'col': f.col,
							'contents': f.contents
						}
						for f in trans.request.hidden_fields
					]
				},
				'response': {
					'screen': trans.response.stringbuffer,
					'rows': trans.response.rows,
					'cols': trans.response.cols,
					'protected_fields': [
						{
							'row': f.row,
							'col': f.col,
							'contents': f.contents,
							'hidden': f.hidden == 1,
							'protected': f.protected == 1
						}
						for f in trans.response.protected_fields
					],
					'input_fields': [
						{
							'row': f.row,
							'col': f.col,
							'contents': f.contents
						}
						for f in trans.response.input_fields
					],
					'hidden_fields': [
						{
							'row': f.row,
							'col': f.col,
							'contents': f.contents
						}
						for f in trans.response.hidden_fields
					]
				},
				'data': [
					{
						'row': f.row,
						'col': f.col,
						'contents': f.contents
					}
					for f in trans.data
				]
			}
			transactions.append(trans_dict)

		with open(filename, 'w', encoding='utf-8') as f:
			if pretty:
				json.dump(transactions, f, indent=2, ensure_ascii=False)
			else:
				json.dump(transactions, f, ensure_ascii=False)

		return True
	except Exception as e:
		print(f"Error exporting to JSON: {e}")
		return False


def export_to_csv(history, filename):
	"""
	Export transaction history to CSV format

	Args:
		history: History object containing transactions
		filename (str): Output file path

	Returns:
		bool: Success status
	"""
	try:
		with open(filename, 'w', newline='', encoding='utf-8') as f:
			writer = csv.writer(f)

			# Write header
			writer.writerow([
				'Transaction ID',
				'Timestamp',
				'Host',
				'Key Pressed',
				'Request Screen (First Line)',
				'Response Screen (First Line)',
				'Modified Fields',
				'Hidden Fields Count',
				'Comment'
			])

			# Write transactions
			for i, trans in enumerate(history):
				request_line = trans.request.stringbuffer[0] if trans.request.stringbuffer else ''
				response_line = trans.response.stringbuffer[0] if trans.response.stringbuffer else ''

				modified_fields = '; '.join([
					f"({f.row},{f.col})={f.contents.strip()}"
					for f in trans.data if f.contents.strip()
				])

				hidden_count = len(trans.response.hidden_fields)

				writer.writerow([
					i,
					trans.timestamp,
					trans.host,
					trans.key,
					request_line.strip(),
					response_line.strip(),
					modified_fields,
					hidden_count,
					trans.comment
				])

		return True
	except Exception as e:
		print(f"Error exporting to CSV: {e}")
		return False


def export_to_html(history, filename):
	"""
	Export transaction history to HTML format

	Args:
		history: History object containing transactions
		filename (str): Output file path

	Returns:
		bool: Success status
	"""
	try:
		html_content = """<!DOCTYPE html>
<html>
<head>
	<meta charset="utf-8">
	<title>BIRP Transaction History</title>
	<style>
		body {
			font-family: 'Courier New', monospace;
			margin: 20px;
			background: #1e1e1e;
			color: #d4d4d4;
		}
		.transaction {
			border: 1px solid #3c3c3c;
			margin: 20px 0;
			padding: 15px;
			background: #252526;
			border-radius: 5px;
		}
		.header {
			color: #4ec9b0;
			font-weight: bold;
			margin-bottom: 10px;
		}
		.screen {
			background: #1e1e1e;
			padding: 10px;
			margin: 10px 0;
			border: 1px solid #3c3c3c;
			white-space: pre;
			overflow-x: auto;
		}
		.field {
			margin: 5px 0;
		}
		.hidden {
			background: #dc3545;
			color: white;
			padding: 2px 4px;
		}
		.modified {
			color: #ffd700;
		}
		.protected {
			color: #6c757d;
		}
		h1 {
			color: #4fc3f7;
		}
		h2 {
			color: #4ec9b0;
			font-size: 1.2em;
		}
		.meta {
			color: #9cdcfe;
			font-size: 0.9em;
		}
	</style>
</head>
<body>
	<h1>BIRP Transaction History</h1>
	<p class="meta">Generated: """ + str(datetime.now()) + """</p>
"""

		for i, trans in enumerate(history):
			html_content += f"""
	<div class="transaction">
		<div class="header">Transaction #{i}</div>
		<div class="meta">
			Timestamp: {trans.timestamp}<br>
			Host: {trans.host}<br>
			Key: {trans.key}<br>
			Comment: {trans.comment}
		</div>

		<h2>Request Screen</h2>
		<div class="screen">{trans.request}</div>

		<h2>Response Screen</h2>
		<div class="screen">{trans.response}</div>
"""

			if trans.data:
				html_content += "\n\t\t<h2>Modified Fields</h2>\n"
				for field in trans.data:
					if field.contents.strip():
						html_content += f'\t\t<div class="field modified">Row: {field.row}, Col: {field.col}, Value: {field.contents.strip()}</div>\n'

			hidden_fields = trans.response.hidden_fields
			if hidden_fields:
				html_content += "\n\t\t<h2>Hidden Fields</h2>\n"
				for field in hidden_fields:
					if field.contents.strip():
						html_content += f'\t\t<div class="field hidden">Row: {field.row}, Col: {field.col}, Value: {field.contents.strip()}</div>\n'

			html_content += "\t</div>\n"

		html_content += """
</body>
</html>
"""

		with open(filename, 'w', encoding='utf-8') as f:
			f.write(html_content)

		return True
	except Exception as e:
		print(f"Error exporting to HTML: {e}")
		return False


def export_to_xml(history, filename):
	"""
	Export transaction history to XML format

	Args:
		history: History object containing transactions
		filename (str): Output file path

	Returns:
		bool: Success status
	"""
	try:
		from xml.etree.ElementTree import Element, SubElement, tostring
		from xml.dom import minidom
		import re

		def sanitize_xml_text(text):
			"""Remove or escape invalid XML characters"""
			if text is None:
				return ''
			# Remove control characters except tab, newline, carriage return
			text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', str(text))
			return text

		root = Element('birpv2_history')

		for i, trans in enumerate(history):
			trans_elem = SubElement(root, 'transaction', id=str(i))

			SubElement(trans_elem, 'timestamp').text = sanitize_xml_text(trans.timestamp)
			SubElement(trans_elem, 'host').text = sanitize_xml_text(trans.host)
			SubElement(trans_elem, 'key').text = sanitize_xml_text(trans.key)
			SubElement(trans_elem, 'comment').text = sanitize_xml_text(trans.comment)

			# Request
			request_elem = SubElement(trans_elem, 'request')
			SubElement(request_elem, 'rows').text = str(trans.request.rows)
			SubElement(request_elem, 'cols').text = str(trans.request.cols)

			screen_elem = SubElement(request_elem, 'screen')
			for line in trans.request.stringbuffer:
				SubElement(screen_elem, 'line').text = sanitize_xml_text(line)

			# Response
			response_elem = SubElement(trans_elem, 'response')
			SubElement(response_elem, 'rows').text = str(trans.response.rows)
			SubElement(response_elem, 'cols').text = str(trans.response.cols)

			screen_elem = SubElement(response_elem, 'screen')
			for line in trans.response.stringbuffer:
				SubElement(screen_elem, 'line').text = sanitize_xml_text(line)

			# Hidden fields
			hidden_elem = SubElement(response_elem, 'hidden_fields')
			for field in trans.response.hidden_fields:
				if field.contents.strip():
					field_elem = SubElement(hidden_elem, 'field')
					SubElement(field_elem, 'row').text = str(field.row)
					SubElement(field_elem, 'col').text = str(field.col)
					SubElement(field_elem, 'contents').text = sanitize_xml_text(field.contents.strip())

			# Modified fields
			data_elem = SubElement(trans_elem, 'modified_fields')
			for field in trans.data:
				if field.contents.strip():
					field_elem = SubElement(data_elem, 'field')
					SubElement(field_elem, 'row').text = str(field.row)
					SubElement(field_elem, 'col').text = str(field.col)
					SubElement(field_elem, 'contents').text = sanitize_xml_text(field.contents.strip())

		# Pretty print
		xml_str = minidom.parseString(tostring(root)).toprettyxml(indent="  ")

		with open(filename, 'w', encoding='utf-8') as f:
			f.write(xml_str)

		return True
	except Exception as e:
		print(f"Error exporting to XML: {e}")
		return False


def auto_export(history, filename):
	"""
	Automatically detect format from filename extension and export

	Args:
		history: History object containing transactions
		filename (str): Output file path (extension determines format)

	Returns:
		bool: Success status
	"""
	filename_lower = filename.lower()

	if filename_lower.endswith('.json'):
		return export_to_json(history, filename)
	elif filename_lower.endswith('.csv'):
		return export_to_csv(history, filename)
	elif filename_lower.endswith('.html') or filename_lower.endswith('.htm'):
		return export_to_html(history, filename)
	elif filename_lower.endswith('.xml'):
		return export_to_xml(history, filename)
	else:
		print(f"Unknown file format. Supported: .json, .csv, .html, .xml")
		return False
