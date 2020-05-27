odoo.define('cap_account_reconciliation.ReconciliationRenderer', function (require) {
    "use strict";

    var ReconciliationRenderer = require("account.ReconciliationRenderer");
    var rpc = require('web.rpc');

    var Widget = require('web.Widget');
    var FieldManagerMixin = require('web.FieldManagerMixin');
    var relational_fields = require('web.relational_fields');
    var basic_fields = require('web.basic_fields');
    var core = require('web.core');
    var time = require('web.time');
    var session = require('web.session');
    var qweb = core.qweb;
    var _t = core._t;

    // UPDATE IN PLACE THE LINE RENDERER CLASS
    ReconciliationRenderer.LineRenderer.include({

        // OVERRIDE METHOD
        update: function (state) {
            // CALL SUPER
            this._super.apply(this, arguments);
            // SET THE MATCH TABLE EMPTY
            var stateMvLines = state.mv_lines || [];
            var $mv_lines = this.$('.match table tbody').empty();
            // FOR EVERY PROPOSITION
            _.each(stateMvLines, function (line) {

                console.log(line.ref);

                // GET THE DEFAULT TEMPLATE
                var $line = $(qweb.render("reconciliation.line.mv_line", {'line': line, 'state': state}));
                if (!isNaN(line.id)) {
                    // ADD THREE COLUMNS: PARTNER NAME, INVOICE STORE ORDER ID, INVOICE CHANNEL NAME
                    $line.find('.cell_label')
                        .after('<td style="text-align: center" class="cell_channel"/>')
                        .after('<td style="text-align: center" class="cell_store_order"/>')
                        .after('<td style="text-align: center" class="cell_partner"/>');
                    // SET DATA FOR THE PARTNER NAME COLUMN
                    if (line.partner_name) {
                        $line.find('.cell_partner').append(document.createTextNode(line.partner_name));
                    }
                   
                    // SET DATA FOR THE INVOICE STORE ORDER ID AND INVOICE CHANNEL NAME COLUMNS
                    if (line.ref) {
                        // TRY TO FIND AN INVOICE NUMBER REFERENCE FROM LINE LABEL OR NAME
//                         var number = "";
//                         if (line.label.startsWith('INV/')) {
//                             number = line.label;
//                         } else if (line.name.startsWith('INV/')) {
//                             number = line.name;
//                         } else if (line.label.includes('IN/')) {
//                             number = line.label.match(/IN\/[^ :\/]*\/[^ :\/]*/g)[0];
//                         } else if (line.name.includes('IN/')) {
//                             number = line.name.match(/IN\/[^ :\/]*\/[^ :\/]*/g)[0];
//                         }
                        // IF WE FOUND ONE CORRECT INVOICE NUMBER
//                         if (number.startsWith('INV/')) {
                            // GET DATA FROM INVOICE
//                             rpc.query({
//                                 model: 'account.move.line',
//                                 method: 'search_read',
//                                 args: [[['ref', '=', line.ref], ['invoice_id', '!=', false]], ['invoice_id']]
//                             }).then(function (result_move) {
                                
//                                 alert(result_move[0]['invoice_id']);
                                rpc.query({
                                model: 'account.move.line',
                                method: 'search_read',
                                args: [[['ref', '=', line.ref]], ['x_store_order_id', 'x_channel_name']]
                                    }).then(function (result) {

                                    
//                                     alert(result[0]['x_store_order_id']);
                                    // SET DATA FOR THE INVOICE STORE ORDER ID COLUMN
                                    if (result.length && result[0]['x_store_order_id']) {
                                        $line.find('.cell_store_order')
                                            .append(document.createTextNode(result[0]['x_store_order_id']));
                                    }
                                    // SET DATA FOR THE INVOICE CHANNEL ID COLUMN
                                    if (result.length && result[0]['x_channel_name']) {
                                        $line.find('.cell_channel')
                                            .append(document.createTextNode(result[0]['x_channel_name']));
                                    }
                                });
//                             });
//                         }
                    }
                    // DO NOT FORGET TO SET UP THE BUBBLE INFO LIKE IN SUPER
                    $('<span class="line_info_button fa fa-info-circle"/>')
                        .appendTo($line.find('.cell_info_popover'))
                        .attr("data-content", qweb.render('reconciliation.line.mv_line.details', {'line': line}));
                }
                // ADD RENDERED PROPOSITION TO THE MATCH TABLE
                $mv_lines.append($line);
            });
        },

    });
});
