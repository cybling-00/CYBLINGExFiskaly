// Copyright (c) 2024, Codes Soft and contributors
// For license information, please see license.txt

frappe.ui.form.on( 'POS Profile', {
	refresh: function ( frm ) {
		show_btn( frm )
	},
	custom_client_id: function ( frm ) {
		show_btn( frm )
	}
} );


function show_btn ( frm ) {
	frm.remove_custom_button( __( 'Create Client ID' ) )
	if ( !cur_frm.doc.__islocal ) {
		if ( !frm.doc.custom_client_id ) {
			frm.add_custom_button( __( 'Create Client ID' ), function () {
				// if (frm.is_dirty()){
				// 	frappe.throw("Document is in not saved state. please save and try again.")
				// }else{
				create_client_id( frm )
				// }
			} );
		}
	}
}

function create_client_id ( frm ) {
	frappe.call( {
		method: 'cyblingexfiskaly.cyblingexfiskaly.doctype.fiskaly_settings.fiskaly_settings.create_client_id',
		freeze: true,
		args: { company: frm.doc.company },
		callback: function ( response ) {
			if ( response ) {
				if ( response.message ) {
					frm.set_value( "custom_client_id", response.message )
					frm.save()
				}
			}
		}
	} )
}