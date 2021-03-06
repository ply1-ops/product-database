from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from app.productdb.forms import ProductMigrationOptionForm
from app.productdb.models import Product, Vendor, ProductGroup, ProductList, ProductMigrationOption, \
    ProductMigrationSource, ProductCheck, ProductCheckEntry, ProductIdNormalizationRule
from app.productdb.models import UserProfile
from django.contrib.auth.models import Permission

admin.site.register(Permission)
admin.site.unregister(User)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = "user profile"
    verbose_name_plural = "user profiles"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "username",
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
        "is_superuser",
        "last_login",
    ]
    inlines = (UserProfileInline, )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "product_id",
        "description",
        "vendor",
        "eox_update_time_stamp",
        "end_of_sale_date",
        "end_of_support_date",
        "has_migration_options",
        "product_migration_source_names",
        "lc_state_sync",
    )

    list_filter = [
        "vendor",
        "lc_state_sync",
        "product_group"
    ]

    search_fields = (
        "product_id",
        "description",
        "tags",
        "vendor__name",
    )

    fieldsets = (
        ("Base data", {
            "fields": (
                "vendor",
                "product_id",
                "description",
                "list_price",
                "currency",
                "internal_product_id",
                "product_group",
                "tags",
                "lc_state_sync",
                "update_timestamp",
                "list_price_timestamp"
            )
        }),
        ("Lifecycle Data", {
            "fields": (
                "eox_update_time_stamp",
                "eol_ext_announcement_date",
                "end_of_sale_date",
                "end_of_new_service_attachment_date",
                "end_of_sw_maintenance_date",
                "end_of_routine_failure_analysis",
                "end_of_service_contract_renewal",
                "end_of_sec_vuln_supp_date",
                "end_of_support_date",
                "eol_reference_number",
                "eol_reference_url"
            )
        })
    )

    readonly_fields = (
        "current_lifecycle_states",
        "has_migration_options",
        "preferred_replacement_option",
        "product_migration_source_names",
        "lc_state_sync",
    )

    def has_migration_options(self, obj):
        return obj.has_migration_options()

    def preferred_replacement_option(self, obj):
        result = obj.get_preferred_replacement_option()
        return result.replacement_product_id if result else ""

    def product_migration_source_names(self, obj):
        return "\n".join(obj.get_product_migration_source_names_set())

    def current_lifecycle_states(self, obj):
        val = obj.current_lifecycle_states
        if val:
            return "<br>".join(obj.current_lifecycle_states)
        return ""

    history_latest_first = True
    ignore_duplicate_revisions = True


@admin.register(ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "vendor"
    )

    search_fields = (
        "name",
        "vendor__name"
    )

    history_latest_first = True
    ignore_duplicate_revisions = True


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    fields = (
        "name",
    )

    history_latest_first = True
    ignore_duplicate_revisions = True


@admin.register(ProductMigrationSource)
class ProductMigrationSourceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "description",
        "preference",
    )

    history_latest_first = True
    ignore_duplicate_revisions = True


@admin.register(ProductMigrationOption)
class ProductMigrationOptionAdmin(admin.ModelAdmin):
    form = ProductMigrationOptionForm
    list_display = (
        "product",
        "replacement_product_id",
        "migration_source",
        "comment",
        "migration_product_info_url",
        "is_replacement_in_db"
    )

    fields = [
        "product_id",
        "replacement_product_id",
        "migration_source",
        "comment",
        "migration_product_info_url",
    ]

    readonly_fields = [
        "is_replacement_in_db"
    ]

    search_fields = (
        "product__product_id",
        "migration_source__name",
    )

    history_latest_first = True
    ignore_duplicate_revisions = True


@admin.register(ProductList)
class ProductListAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "description",
        "update_user",
        "update_date",
        "hash"
    ]
    fields = [
        "name",
        "description",
        "string_product_list",
        "version_note",
        "update_user",
        "update_date",
        "hash"
    ]

    readonly_fields = [
        "update_date"
    ]

    history_latest_first = True
    ignore_duplicate_revisions = True


@admin.register(ProductCheck)
class ProductCheckAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "migration_source",
        "last_change",
        "create_user",
        "in_progress",
        "id",
    ]
    fields = [
        "name",
        "migration_source",
        "input_product_ids",
        "last_change",
        "create_user",
        "task_id"
    ]

    readonly_fields = [
        "last_change",
        "in_progress",
        "input_product_ids"
    ]

    history_latest_first = True
    ignore_duplicate_revisions = True


@admin.register(ProductCheckEntry)
class ProductCheckEntryAdmin(admin.ModelAdmin):
    list_display = [
        "product_check",
        "input_product_id",
        "product_in_database",
        "in_database",
        "amount",
        "migration_product_id",
    ]
    fields = [
        "product_check",
        "input_product_id",
        "product_in_database",
        "in_database",
        "amount",
        "migration_product_id",
        "part_of_product_list"
    ]

    readonly_fields = [
        "product_in_database",
        "in_database",
        "migration_product_id",
        "part_of_product_list"
    ]

    history_latest_first = True
    ignore_duplicate_revisions = True


@admin.register(ProductIdNormalizationRule)
class ProductIdNormalizationRuleAdmin(admin.ModelAdmin):
    list_display = [
        "product_id",
        "regex_match",
        "priority",
        "vendor",
        "comment"
    ]

    list_filter = [
        "vendor",
    ]
    search_fields = [
        "product_id",
        "regex_match",
        "vendor__name",
        "comment"
    ]
    ordering = [
        "vendor",
        "priority",
        "product_id"
    ]
    actions = [
        "update_entry"
    ]

    history_latest_first = True
    ignore_duplicate_revisions = True
