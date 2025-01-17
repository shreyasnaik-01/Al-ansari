# Copyright (c) 2022, Indictrans and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
from frappe import _

class EarnedLeaveDeductions(Document):
	# pass
	def on_submit(self):
		self.negative_leave_allocation()

	def negative_leave_allocation(self):
		allocation_issue = []
		for i in self.deduction_ratio:
			if i.to_be_deducted >0:
				existing_rec= frappe.get_list('Leave Allocation',
					fields= ["name"],
					filters= [
							['from_date',"=",frappe.utils.add_months(self.from_date, 1)],
							['to_date',"=",frappe.utils.add_months(self.to_date, 1)],
							['employee',"=",i.employee_id],
							['leave_type',"=", "Annual Leave"],
							]
					)
				if existing_rec:
					allocation_issue.append(i.employee_id)
				else:
					leave_alloc = frappe.new_doc("Leave Allocation")
					leave_alloc.employee = i.employee_id
					leave_alloc.employee_name = i.employee_name
					leave_alloc.leave_type= "Annual Leave"
					leave_alloc.new_leaves_allocated = -(i.to_be_deducted)
					leave_alloc.from_date = frappe.utils.add_months(self.from_date, 1) # frm.get("from_date")
					leave_alloc.to_date = frappe.utils.add_months(self.to_date, 1) # frm.get("to_date")
					leave_alloc.save()
					leave_alloc.submit()
			else:
				# frappe.throw("No record for making negative entry")
				allocation_issue.append(i.employee_id)

		if len(allocation_issue) >0:
			frappe.throw(_("The entries for the following emplyoees couldn't be done as they may already exist. Please try entering them manually if required and remove from the table to proceed with other records.({0})").format(allocation_issue))
		else:
			frappe.msgprint(_("Allocation records created successfully"))


@frappe.whitelist()
def no_of_working_days_employeewise(frm):
	frm = frappe.json.loads(frm)

	days_of_month = frappe.db.sql("""SELECT DAYOFMONTH(LAST_DAY(%s)) as days_of_month""",(frm.get("from_date")),as_dict=1)[0].days_of_month

	deduction_ratio = frm.get("deduction_ratio")
	working_days = []
	for item in deduction_ratio:
		holiday_count = frappe.db.sql(""" 
				Select count(*) as h_count from `tabHoliday` h,`tabHoliday List` hl, `tabEmployee` e 
				where h.parent=hl.name  
				and e.holiday_list = hl.name 
				and e.name = %s 
				and h.holiday_date between %s and %s;
			""",(item["employee_id"],frm.get("from_date"),frm.get("to_date")),as_dict=1)[0].h_count
		# print("holiday_count=====>",holiday_count)
		# get leave allocation per month
		# el_allocated = frappe.db.get_value("Leave Allocation",{'employee':item["employee_id"],"leave_type":"Annual Leave"},['monthly_el_allocated']) or 0
		el_allocated = frappe.db.get_value("Leave Type",{'name':"Annual Leave"},['monthly_allocation']) or 0
		
		# get No. of LWP (summation of fraction of LWP on Leave application)
		no_of_lwp = frappe.db.sql(""" 
			SELECT employee,sum(fraction_of_daily_wage) as no_of_lwp 
			from `tabLeave Application` 
			where employee = %s 
			and docstatus = 1
			and from_date >= %s
			and to_date <= %s
			""",(item["employee_id"],frm.get("from_date"),frm.get("to_date")),as_dict=1)[0].no_of_lwp or 0
		print("no_of_lwp=",no_of_lwp)

		no_of_lwp_manual = frappe.db.sql(""" 
			SELECT la.employee,sum(la.total_leave_days) as no_of_lwp
			from `tabLeave Application` la , `tabLeave Type` lt 
			where la.leave_type = lt.name 
			and la.employee = %s 
			and la.docstatus = 1
			and la.from_date >= %s
			and la.to_date <= %s
			and la.fraction_of_daily_wage = 0
			and lt.is_lwp = 1
			""",(item["employee_id"],frm.get("from_date"),frm.get("to_date")),as_dict=1)[0].no_of_lwp or 0
		print("no_of_lwp_manual== ",no_of_lwp_manual)
		if holiday_count:
			working_days.append({"employee":item["employee_id"],"no_of_working_days":(days_of_month-holiday_count),"el_allocated":el_allocated,"no_of_lwp":no_of_lwp+no_of_lwp_manual})
		else:
			working_days.append({"employee":item["employee_id"],"no_of_working_days":days_of_month,"el_allocated":el_allocated,"no_of_lwp":no_of_lwp+no_of_lwp_manual})

	return working_days

@frappe.whitelist()
def get_applicants(frm):
	frm = frappe.json.loads(frm)

	return frappe.db.sql(""" 
				SELECT 
					DISTINCT(employee),
					employee_name
				from `tabLeave Application`
				where 
				from_date >= %s
				and to_date <= %s""",(frm.get("from_date"),frm.get("to_date")),as_dict=1)