# coding=utf-8
"""
Mixins contain multilookup script
"""
# coding=utf-8

from functools import reduce

from django.contrib.contenttypes.fields import GenericRelation
from django.db.models import Q
from drf_writable_nested import (
    WritableNestedModelSerializer,
    UniqueFieldsMixin, NestedUpdateMixin,
)

from rest_framework.exceptions import ValidationError


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
                    field_name, instance, field, related_data
                )
            elif self.__get_lookup_field(field):
                instances = self._prefetch_related_instances_by_lookup(
                    field_name, instance, field, related_data
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
                    obj = instances.get(data.get(
                        self.__get_combined_key(
                            data,
                            self.__get_lookup_fields(field)
                        )))
                elif self.__get_lookup_field(field):
                    obj = instances.get(
                        data.get(self.__get_lookup_field(field))
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
                                              field, related_data):
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
        lookup_filter = {
            f"{self.__get_lookup_field(field)}__in": lookup_field_values
        }
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
                                               field, related_data):
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
        lookup_filter = reduce(lambda a, b: a | b, args)
        instances = {
            self.__get_combined_key(
                related_data,
                self.__get_lookup_fields(field)
            ): related_instance
            for related_instance in getattr(instance, field_name).
            filter(*lookup_filter)
        }
        return instances

    def __get_combined_key(self, lookup_fields, related_data):
        keys = [
            f"{related_data.get(field, '0')}" for field in lookup_fields
        ]
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
                if pk:
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
            if self.__get_lookup_fields(field):
                single_instance = {}
                for field_name in self.__get_lookup_fields(field):
                    pk = data.get(field_name)
                    if pk:
                        single_instance.update({
                            field_name: pk
                        })
                if single_instance:
                    obj = model_class.objects.filter(
                        **single_instance
                    ).first()
            elif self.__get_lookup_field(field):
                pk = data.get(self.__get_lookup_field(field))
                if pk:
                    obj = model_class.objects.filter(
                        **{self.__get_lookup_field(field): pk}
                    ).first()
            else:
                pk = self._get_related_pk(data, model_class)
                if pk:
                    obj = model_class.objects.filter(
                        pk=pk,
                    ).first()
            serializer = self._get_serializer_for_field(
                field,
                instance=obj,
                data=data,
            )

            try:
                serializer.is_valid(raise_exception=True)
                attrs[field_source] = serializer.save(
                    **self._get_save_kwargs(field_name)
                )
            except ValidationError as exc:
                raise ValidationError({field_name: exc.detail})