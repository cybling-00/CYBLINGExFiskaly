// Copyright (c) 2024, Codes Soft and contributors
// For license information, please see license.txt

frappe.ui.form.on( 'Fiskaly Settings', {
	refresh: function ( frm ) {
		frm.add_custom_button(__('Refresh Token'), function() {
			frm.set_value("token", "")
			frm.save()
		});
	}
} );


function disable_all_previous_tss () {
	frappe.call( {
		method: 'cyblingexfiskaly.cyblingexfiskaly.doctype.fiskaly_settings.fiskaly_settings.disable_all_previous_tss',
		freeze: true,
		// args: {},
		callback: function ( response ) {
			if ( response ) {
				if ( response.message ) {
					frm.reload_doc()
				}
			}
		}
	} )
}