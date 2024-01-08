# 2022/09/06 - Dynamically loading keys & constraints in Python Schemas

*Originally published on [Medium](https://medium.com/carsdotcom-technology/dynamically-loading-keys-constraints-in-python-schemas-1d6106586da0)*

---

*Gabe is a Data Engineering intern at Cars.com who has been programming in Python 3 for over 8 years. This article is
based on an issue found within an internal application used to automate the management of AWS EC2
instances. The code discussed in this article allowed for the dynamic validation of user configuration options to be set
within the
admin configuration.*

When programming using Python Schemas, it can be useful to dynamically load options to check against the schema, such as
when you are unsure what options may be loaded from a configuration file but you want the security provided.
This can be difficult to implement, especially when there are constraints that must be checked against. The Schema
package, to my knowledge and research, does not have any way to do this to my knowledge. Furthermore, the way in which
constraints are handled mean that you cannot get the key when checking the constraints and vice versa, making it quite
tough to check the constraints in an efficient manner. This is where the `nonlocal` keyword comes into play.

To start, let’s begin with this YAML:

```yaml
config:
  - name: x                 # Key
    type: y                 # Type
    constraints: [ foo, bar ] # List of values we want to constrain to
```

We want to load the data in config, but ensure that we maintain type checking and constraints. However, we have no way
to check the key, nor any of the constraints. To do this, we’ll create a number of inner functions. For this example, we
need three functions to check the key, the type and the constraints, but this can be easily expanded or changed to fit
different constraints. We create a variable to store the key, and that will act as a shared state between all the
functions. This is operating with the presumption that the Schema will be checked sequentially, but this doesn’t
guarantee atomicity during multithreading.

```python
config = load_config()  # Pseudo code to load the config abovekey = None


def _key_check(x):
    nonlocal key
    key = x
    return x in [option['name] for option in config]def _is_constrained(x):
                 constraints = list(filter(lambda n: n['name'] == key, config))[0]['constraints']
    if not constraints:
        return True
    return x in constraintsdef
    _get_type(x):
    type_str = list(filter(lambda n: n['name'] == key, config))[0]['type']
    return isinstance(x, eval(type_str))
```

It is important to remember with this that `eval` is a dangerous function, but the input should always be known and set
in the config being passed. For a situation where one is dynamically loading config options and using this to set what
can be loaded, the input into `eval` should be known and therefore somewhat safe. In all of these, `x` is what will be
passed to the function by Schema, be it the key or the value of the key. With `key` holding the current key being
evaluated, we can use this to grab the values we need from the config and check that we’re only getting what we need.
The Schema then is quite simple to set up, and for this could be as simple as:

```python
Schema({
    Optional(_key_check): And(_get_type, _is_constrained)
})
```

And with that, it’s quite simple to check any dynamic data and confirm it does follow constraints and type checking.