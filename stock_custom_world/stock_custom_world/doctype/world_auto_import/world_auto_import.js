// Copyright (c) 2025, IECMU and contributors
// For license information, please see license.txt

frappe.ui.form.on("World Auto Import", {
	setup(frm) {
		console.log("setup");
		// Setup custom function
		frm.has_import_file = () => {
			return Boolean(frm.doc.import_file);
		};

		// Set up progress bar
		frappe.realtime.on("data_import_progress", (data) => {
			console.log("real_time", data);

			frm.dashboard.show_progress("Importing Data", data.progress, data.description);

			if (data.progress === 100) {
				setTimeout(() => {
					// frm.reload_doc();
				}, 500);
			}
		});
	},

	refresh(frm) {
		console.log("refresh", frm);
		frm.refresh_fields();
		frm.trigger("update_primary_action");
	},

	import_file(frm) {
		console.log("checkin_file");
		frm.trigger("update_primary_action");
	},

	start_import(frm) {
		console.log("start_import");
		frm.call({
			method: "form_start_import",
			args: { doc_name: frm.doc.name },
			btn: frm.page.btn_primary,
		}).then((r) => {
			console.log(r);
			frm.refresh();
		});
	},

	update_primary_action(frm) {
		console.log({
			_where: "update_primary_section",
			frm,
			is_new: frm.is_new(),
			status: frm.doc.status,
			has_import: frm.has_import_file(),
		});
		// console.log("update_primary_action");
		// if (frm.is_dirty()) {
		//   frm.enable_save();
		//   return;
		// }
		// frm.disable_save();

		if (frm.doc.status !== "SUCCESS") {
			if (!frm.is_new() && frm.has_import_file()) {
				let label = __("Start Import");
				frm.page.set_primary_action(label, () => frm.events.start_import(frm));
			} else {
				frm.page.set_primary_action(__("Save"), () => frm.save());
			}
		}
	},
});
