// Copyright (c) 2024, Codes Soft and contributors
// For license information, please see license.txt

frappe.ui.form.on( 'Company', {
	refresh: function ( frm ) {
		show_btn( frm )
	},
	custom_technical_security_system_tss_id: function ( frm ) {
		show_btn( frm )
	}
} );


function show_btn ( frm ) {
	frm.remove_custom_button( __( 'Create TSS ID' ) )
	if ( !cur_frm.doc.__islocal ) {
		if ( !frm.doc.custom_technical_security_system_tss_id ) {
			frm.add_custom_button( __( 'Create TSS ID' ), function () {
				// if (frm.is_dirty()){
				// 	frappe.throw("Document is in not saved state. please save and try again.")
				// }else{
				create_tss_id( frm )
				// }
			} );
		}
	}
}

function create_tss_id ( frm ) {
	let admin_pin = "1234567890"
	frappe.call( {
		method: 'cyblingexfiskaly.cyblingexfiskaly.doctype.fiskaly_settings.fiskaly_settings.create_tss_id',
		freeze: true,
		args: { admin_pin : admin_pin },
		callback: function ( response ) {
			if ( response ) {
				if ( response.message ) {
					frm.set_value( "custom_technical_security_system_tss_id", response.message )
					frm.set_value( "custom_tss_pin", admin_pin )
					frm.save()
				}
			}
		}
	} )
}