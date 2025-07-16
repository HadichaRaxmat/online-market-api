from django.db import models, connection

OPERATORS = {
    'lt': '<',
    'lte': '<=',
    'gt': '>',
    'gte': '>=',
    'exact': '=',
    'icontains': 'LIKE',
}


class CustomSQLManager(models.Manager):
    def custom_filter(self, **kwargs):
        table_name = self.model._meta.db_table  # автоматически узнаёт имя таблицы из модели
        sql = f"SELECT * FROM {table_name}"
        conditions = []
        values = []

        for key, value in kwargs.items():
            if "__" in key:
                field, op = key.split("__")
                sql_op = OPERATORS.get(op)
                if not sql_op:
                    raise ValueError(f"Оператор {op} не поддерживается")
                if op == "icontains":
                    conditions.append(f"{field} {sql_op} %s")
                    values.append(f"%{value}%")
                else:
                    conditions.append(f"{field} {sql_op} %s")
                    values.append(value)
            else:
                conditions.append(f"{key} = %s")
                values.append(value)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        with connection.cursor() as cursor:
            cursor.execute(sql, values)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

        return [dict(zip(columns, row)) for row in rows]
