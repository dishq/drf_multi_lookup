# coding=utf-8
"""
Mixins contain multilookup script
"""
# coding=utf-8

from functools import reduce
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.contenttypes.fields import GenericRelation
from django.db.models import Q
from drf_writable_nested import (
    UniqueFieldsMixin, NestedUpdateMixin,
)

from rest_framework.exceptions import ValidationError
from rest_framework import serializers


class MultiLookUpMixin(UniqueFieldsMixin, NestedUpdateMixin):
    """
    Add a layer of multilook up fields before so that we can avoid a ton of
    boiler plate code
    """

    def update_or_create_reverse_relations(self, instance, reverse_relations):
        """
        Update or create reverse relations:
        many-to-one, many-to-many, reversed one-to-one

        :param instance:
        :param reverse_relations:
        :return:
        """

        for field_name, (related_field, field, field_source) in \
                reverse_relations.items():
            # Skip processing for empty data or not-specified field.
            # The field can be defined in validated_data but isn't defined
            # in initial_data (for example, if multipart form data used)
            related_data = self.get_initial().get(field_name, None)
            if related_data is None:
                continue

            if related_field.one_to_one:
                # If an object already exists, fill in the pk so
                # we don't try to duplicate it
                pk_name = field.Meta.model._meta.pk.attname
                if pk_name not in related_data and 'pk' in related_data:
                    pk_name = 'pk'
                if pk_name not in related_data:
                    related_instance = getattr(instance, field_source, None)
                    if related_instance:
                        related_data[pk_name] = related_instance.pk

                # Expand to array of one item for one-to-one for uniformity
                related_data = [related_data]

            if self.__get_lookup_fields(field):
                instances = self._prefetch_related_instances_by_lookups(
                    field_name, instance, field, related_data, related_field
                )
            elif self.__get_lookup_field(field):
                instances = self._prefetch_related_instances_by_lookup(
                    field_name, instance, field, related_data, related_field
                )
            else:
                instances = self._prefetch_related_instances(
                    field, related_data
                )

            save_kwargs = self._get_save_kwargs(field_name)
            if isinstance(related_field, GenericRelation):

                save_kwargs.update(
                    self._get_generic_lookup(instance, related_field),
                )
            elif not related_field.many_to_many:
                save_kwargs[related_field.name] = instance

            new_related_instances = []
            errors = []
            for data in related_data:
                if self.__get_lookup_fields(field):
                    if related_field.many_to_many:
                        instance_pk = None
                    else:
                        instance_pk = instance.pk

                    obj = instances.get(
                        self.__get_combined_key(
                            data,
                            self.__get_lookup_fields(field),
                            instance_pk
                        ))
                elif self.__get_lookup_field(field):
                    obj = instances.get(
                        str(data.get(self.__get_lookup_field(field)))
                    )
                else:
                    obj = instances.get(
                        self._get_related_pk(data, field.Meta.model)
                    )
                serializer = self._get_serializer_for_field(
                    field,
                    instance=obj,
                    data=data,
                )
                try:
                    serializer.is_valid(raise_exception=True)
                    serializer.has_parent = True
                    related_instance = serializer.save(**save_kwargs)
                    data['pk'] = related_instance.pk
                    new_related_instances.append(related_instance)
                    errors.append({})
                except ValidationError as exc:
                    errors.append(exc.detail)

            if any(errors):
                if related_field.one_to_one:
                    raise ValidationError({field_name: errors[0]})
                else:
                    raise ValidationError({field_name: errors})

            if related_field.many_to_many:
                # Add m2m instances to through model via add
                m2m_manager = getattr(instance, field_source)
                m2m_manager.add(*new_related_instances)

    def __get_lookup_fields(self, field):
        """
        Overwrite hasattr first
        :return:
        """
        if hasattr(field.Meta, "lookup_fields"):
            return field.Meta.lookup_fields
        return []

    def __get_lookup_field(self, field):
        """
        Overwrite hasattr first
        :return:
        """
        if hasattr(field.Meta, "lookup_field"):
            return field.Meta.lookup_field
        return None

    def _prefetch_related_instances_by_lookup(self, field_name, instance,
                                              field, related_data,
                                              related_field):
        """
        Lookup if look up is present or take pk
        :param field_name:
        :param instance:
        :param field:
        :param related_data:
        :return:
        """
        lookup_field_values = self._get_lookup_field_values(
            field,
            related_data
        )
        model_class = field.Meta.model
        lookup_filter = {
            "{}__in".format(self.__get_lookup_field(field)):
                lookup_field_values
        }

        if related_field.many_to_many:
            instances = {
                str(
                    getattr(related_instance, self.__get_lookup_field(field))
                ): related_instance
                for related_instance in model_class.objects.
                filter(**lookup_filter)
            }

            return instances
        instances = {
            str(
                getattr(related_instance, self.__get_lookup_field(field))
            ): related_instance
            for related_instance in getattr(instance, field_name).filter(
                **lookup_filter
            )
        }
        return instances

    def _prefetch_related_instances_by_lookups(self,
                                               field_name,
                                               instance,
                                               field, related_data,
                                               related_field):
        """
        Lookup if look up is present or take pk
        :param field_name:
        :param instance:
        :param field:
        :param related_data:
        :return:
        """

        lookup_field_values = self._get_lookup_fields_values(
            field,
            related_data
        )

        args = [
            Q(**lookup_field_value)
            for lookup_field_value in lookup_field_values
        ]
        model_class = field.Meta.model
        # no filter to apply
        if not args:
            return {}
        # should not reach here if args are empty
        lookup_filter = reduce(lambda a, b: a | b, args)
        instances = {}
        if related_field.many_to_many:
            instances = {
                self.__get_combined_key_from_instance(
                    related_instance,
                    self.__get_lookup_fields(field)
                ): related_instance
                for related_instance in model_class.objects.
                filter(lookup_filter)
            }

            return instances

        instances.update({
            self.__get_combined_key_from_instance(
                related_instance,
                self.__get_lookup_fields(field),
                instance.pk
            ): related_instance
            for related_instance in getattr(instance, field_name).
            filter(lookup_filter)
        })
        return instances

    def __get_combined_key(self, related_data, lookup_fields,
                           instance=None):

        keys = [
            "{}".format(
                related_data.get(field, '0')
            ) for field in lookup_fields
        ]
        if instance:
            keys = keys + [str(instance.pk)]
        return "-".join(keys)

    def __get_combined_key_from_instance(
            self, related_instance, lookup_fields, instance=None
    ):
        keys = [
            "{}".format(
                getattr(related_instance, field)
            ) for field in lookup_fields
        ]
        if instance:
            keys = keys + [str(instance.pk)]
        return "-".join(keys)

    def _get_lookup_field_values(self, field, related_data):
        """
        Get lookup field value from data
        :param self:
        :param related_data:
        :return:
        """
        model_class = field.Meta.model
        pk_list = []
        for d in filter(None, related_data):
            pk = d.get(self.__get_lookup_field(field))
            if pk:
                pk_list.append(pk)

        return pk_list

    def _get_lookup_fields_values(self, field, related_data):
        """
        Get lookup field value from data
        :param self:
        :param related_data:
        :return:
        """
        model_class = field.Meta.model
        pk_list = []
        for d in filter(None, related_data):
            single_instance = {}
            for field_name in self.__get_lookup_fields(field):
                pk = d.get(field_name)
                if pk is not None:
                    single_instance.update({
                        field_name: pk
                    })
            if single_instance:
                pk_list.append(single_instance)
        return pk_list

    def update_or_create_direct_relations(self, attrs, relations):
        """
        Foreignkey override with lookup_field
        :param attrs:
        :param relations:
        :return:
        """

        for field_name, (field, field_source) in relations.items():
            obj = None
            data = self.get_initial()[field_name]
            model_class = field.Meta.model
            if self._get_related_pk(data, model_class):
                pk = self._get_related_pk(data, model_class)
                if pk is not None:
                    try:
                        obj = model_class.objects.get(
                            pk=pk,
                        )
                    except ObjectDoesNotExist:
                        raise serializers.ValidationError(
                            "It is either deleted or soft deleted"
                        )
            elif self.__get_lookup_fields(field):
                single_instance = {}
                for field_name in self.__get_lookup_fields(field):
                    pk = data.get(field_name)
                    if pk is not None:
                        single_instance.update({
                            field_name: pk
                        })
                if single_instance:
                    obj = model_class.objects.filter(
                        **single_instance
                    ).first()
            elif self.__get_lookup_field(field):
                pk = data.get(self.__get_lookup_field(field))
                if pk is not None:
                    obj = model_class.objects.filter(
                        **{self.__get_lookup_field(field): pk}
                    ).first()
            else:
                pk = self._get_related_pk(data, model_class)
                if pk is not None:
                    try:
                        obj = model_class.objects.get(
                            pk=pk,
                        )
                    except ObjectDoesNotExist:
                        raise serializers.ValidationError(
                            "It is either deleted or soft deleted"
                        )
            serializer = self._get_serializer_for_field(
                field,
                instance=obj,
                data=data,
            )

            try:
                serializer.is_valid(raise_exception=True)
                serializer.has_parent = True
                attrs[field_source] = serializer.save(
                    **self._get_save_kwargs(field_name)
                )
            except ValidationError as exc:
                raise ValidationError({field_name: exc.detail})

    def create(self, validated_data):
        """
        Check if Meta has lookup_fields
        :param validated_data:
        :return:
        """
        if hasattr(self, "has_parent") and getattr(self, "has_parent"):
            return super(
                MultiLookUpMixin,
                self
            ).create(validated_data)

        if self.instance is None:
            model_class = self.Meta.model
            lookup_field = self.__get_lookup_field(self)
            lookup_fields = self.__get_lookup_fields(self)
            if self._get_related_pk(self.initial_data, model_class):
                pk = self._get_related_pk(self.initial_data, model_class)
                if pk:
                    self.instance = model_class.objects.get(
                        pk=pk,
                    )
            elif lookup_field:
                self.instance = model_class.objects.filter(
                    **{
                        lookup_field:
                            self.initial_data[lookup_field]
                    }
                ).first()
            elif lookup_fields:
                self.instance = model_class.objects.filter(
                    **{
                        field: self.initial_data[field]
                        for field in lookup_fields
                    }
                ).first()

        if self.instance:
            return self.update(self.instance, validated_data)
        else:
            return super(
                MultiLookUpMixin,
                self
            ).create(validated_data)


class ReadOnlyMultiLookupMixin(MultiLookUpMixin):
    """
    can only read no update or create
    """

    def update(self, instance, validated_data):
        """
        No Update ingredient form
        :param instance:
        :param validated_data:
        :return:
        """
        return instance

    def create(self, validated_data):
        """
        No Update ingredient form
        :param instance:
        :param validated_data:
        :return:
        """
        raise serializers.ValidationError("No Existing {} instance".format(
            self.Meta.model.__class__.__name__)
        )
